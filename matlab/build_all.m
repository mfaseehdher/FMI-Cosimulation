function build_all(selected, export_fmus)
% Pipeline 1: load checked-in SLX models, export FMUs, simulate MATLAB references.
if nargin < 1, selected = ''; end
if nargin < 2, export_fmus = true; end
root = fileparts(fileparts(mfilename('fullpath')));
records = experiment_cases(selected);
assert(~isempty(which('exportToFMU')), 'Simulink FMU Builder is required.');
build = fullfile(root, 'build');
if ~exist(build, 'dir'), mkdir(build); end
scratch = tempname(build);
mkdir(scratch);
original = pwd;
cleanup_dir = onCleanup(@() cd(original));
cd(scratch);
environment.matlab_version = version;
environment.matlab_root = matlabroot;
environment.platform = computer;
products = ver;
environment.products = {products.Name};
environment.fmu_exports_requested = export_fmus;
[~, environment.build_id] = fileparts(scratch);
environment.experiment_ids = {records.metadata};
environment.experiment_ids = cellfun(@(m) m.id, environment.experiment_ids, 'UniformOutput', false);
environment.build_complete = false;
compiler = mex.getCompilerConfigurations('C', 'Selected');
environment.compiler = 'not selected';
if ~isempty(compiler), environment.compiler = compiler.Name; end
write_json(fullfile(build, 'matlab_environment.json'), environment);
fprintf('MATLAB %s; exports requested: %d\n', version, export_fmus);
for k = 1:numel(records)
    item = records(k);
    fprintf('\n=== %s ===\n', item.metadata.id);
    for folder = {'fmus', 'reference'}
        if ~exist(fullfile(item.folder, folder{1}), 'dir'), mkdir(fullfile(item.folder, folder{1})); end
    end
    names = fieldnames(item.config.components);
    for n = 1:numel(names)
        spec = item.config.components.(names{n});
        if ~strcmp(spec.type, 'fmu'), continue; end
        [~, model] = fileparts(spec.file);
        file = fullfile(item.folder, 'models', [model '.slx']);
        assert(isfile(file), 'Missing SLX file. Run prepare_models before build_all.');
        if ~export_fmus, continue; end
        load_system(file);
        cleanup_model = onCleanup(@() close_system(model, 0));
        exportToFMU(model, 'FMIVersion', '2.0', 'FMUType', 'CS', 'EnableFMUState', 'on', ...
            'SaveDirectory', fullfile(item.folder, 'fmus'), ...
            'ExportedParameters', {'loop_gain'}, 'ExportedParameterNames', {'Gain'}, ...
            'ExportedInputNames', {'Bias', 'Feedback'}, 'ExportedOutputNames', {'Out'});
        clear cleanup_model;
    end
    generate_reference(item, environment.build_id);
end
environment.build_complete = true;
write_json(fullfile(build, 'matlab_environment.json'), environment);
end

function generate_reference(item, build_id)
cfg = item.config;
meta = item.metadata;
model = ['reference_' meta.id];
folder = fullfile(item.folder, 'reference');
file = fullfile(item.folder, 'models', [model '.slx']);
assert(isfile(file), 'Missing coupled reference SLX model.');
load_system(file);
cleanup = onCleanup(@() close_system(model, 0));
status.id = meta.id;
status.build_id = build_id;
status.matlab_version = version;
status.model_file = ['models/' model '.slx'];
status.reference_alignment = meta.reference_alignment;
try
    result = sim(model, 'ReturnWorkspaceOutputs', 'on');
catch exception
    status.status = 'UNEXPECTED_FAILURE';
    status.error_identifier = exception.identifier;
    status.error_message = exception.message;
    status.error_report = getReport(exception, 'extended', 'hyperlinks', 'off');
    expected = strcmp(meta.matlab_expectation, 'algebraic_failure') ...
        && strcmp(exception.identifier, 'Simulink:Engine:AlgLoopTroubleInFixedStepNoSolverSwitch');
    if expected, status.status = 'EXPECTED_ALGEBRAIC_FAILURE'; end
    write_json(fullfile(folder, 'reference_status.json'), status);
    if ~expected, rethrow(exception); end
    fprintf('Expected MATLAB algebraic-loop failure: %s\n', exception.identifier);
    return;
end
assert(strcmp(meta.matlab_expectation, 'success'), ...
    'An inconsistent reference unexpectedly simulated successfully.');
logs = cfg.connections(strcmp({cfg.connections.dst_comp}, 'log'));
raw = table;
for k = 1:numel(logs)
    port = logs(k).dst_port;
    signal = result.get(['ref_' port]);
    time = double(signal.Time(:));
    values = double(signal.Data(:));
    assert(numel(time) == numel(values), 'Only scalar adder signals are supported.');
    assert(all(isfinite(values)), 'MATLAB produced non-finite reference values.');
    if k == 1
        raw.time = time;
    else
        assert(numel(raw.time) == numel(time) && all(abs(raw.time - time) < 1e-12), ...
            'MATLAB logging channels use different sample times.');
    end
    raw.(port) = values;
end
writetable(raw, fullfile(folder, 'matlab_trace.csv'));
count = round((cfg.stop - cfg.start) / cfg.dt);
starts = cfg.start + (0:count-1)' * cfg.dt;
indices = zeros(count, 1);
for k = 1:count
    matches = find(abs(raw.time - starts(k)) < 1e-10);
    assert(numel(matches) == 1, 'Missing or duplicated reference sampling point.');
    indices(k) = matches;
end
% Stateless adders keep these values throughout the input-held interval.
% Preserve the raw sampling time; do not disguise this as an end-time sample.
comparison = raw(indices, :);
comparison.reference_sample_time = comparison.time;
comparison.time = round(starts + cfg.dt, 12);
comparison = movevars(comparison, 'reference_sample_time', 'After', 'time');
writetable(comparison, fullfile(folder, 'reference.csv'));
status.status = 'SUCCESS';
status.samples = height(comparison);
status.raw_samples = height(raw);
status.logged_signals = {logs.dst_port};
status.time_semantics = 'time is interval end; reference_sample_time is actual MATLAB sample at interval start';
write_json(fullfile(folder, 'reference_status.json'), status);
fprintf('MATLAB reference: %d raw points; %d comparison intervals.\n', height(raw), height(comparison));
end

function write_json(path, value)
file = fopen(path, 'w');
assert(file >= 0, 'Cannot open JSON output.');
cleanup = onCleanup(@() fclose(file));
fprintf(file, '%s\n', jsonencode(value, 'PrettyPrint', true));
end
