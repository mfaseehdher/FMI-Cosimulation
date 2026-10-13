function prepare_models(selected)
% Create missing source SLX files. Existing models are never overwritten.
if nargin == 0, selected = ''; end
assert(~isempty(which('new_system')), 'Simulink is not installed.');
records = experiment_cases(selected);
for k = 1:numel(records)
    item = records(k);
    cfg = item.config;
    folder = fullfile(item.folder, 'models');
    if ~exist(folder, 'dir'), mkdir(folder); end
    names = fieldnames(cfg.components);
    for n = 1:numel(names)
        spec = cfg.components.(names{n});
        if ~strcmp(spec.type, 'fmu'), continue; end
        [~, model] = fileparts(spec.file);
        file = fullfile(folder, [model '.slx']);
        if isfile(file), continue; end
        new_system(model);
        cleanup = onCleanup(@() close_system(model, 0));
        workspace = get_param(model, 'ModelWorkspace');
        assignin(workspace, 'loop_gain', Simulink.Parameter(spec.parameters.Gain));
        set_param(model, 'ParameterArgumentNames', 'loop_gain');
        add_adder_blocks(model, 'loop_gain');
        set_param(model, 'SolverType', 'Fixed-step', 'Solver', 'FixedStepDiscrete', ...
            'FixedStep', num2str(item.metadata.internal_step, 17), ...
            'StartTime', num2str(cfg.start, 17), 'StopTime', num2str(cfg.stop, 17));
        save_system(model, file);
        clear cleanup;
    end
    reference = ['reference_' item.metadata.id];
    file = fullfile(folder, [reference '.slx']);
    if ~isfile(file)
        new_system(reference);
        cleanup = onCleanup(@() close_system(reference, 0));
        create_reference(reference, cfg, item.metadata);
        save_system(reference, file);
        clear cleanup;
    end
    fprintf('Prepared existing/missing models: %s\n', item.metadata.id);
end
end

function create_reference(model, cfg, meta)
source = cfg.components.source;
ports = unique({cfg.connections(strcmp({cfg.connections.src_comp}, 'source')).src_port}, 'stable');
for k = 1:numel(ports)
    port = ports{k};
    path = [model '/src_' port];
    position = [35 40 + 65*k 85 70 + 65*k];
    if strcmp(source.type, 'const')
        add_block('simulink/Sources/Constant', path, 'Value', num2str(source.values.(port), 17), ...
            'OutDataTypeStr', 'double', 'Position', position);
    else
        signal = source.ports.(port);
        when = 0;
        if isfield(signal, 'step_time'), when = signal.step_time; end
        add_block('simulink/Sources/Step', path, ...
            'Time', num2str(when, 17), 'Before', num2str(signal.initial, 17), ...
            'After', num2str(signal.step, 17), ...
            'SampleTime', num2str(meta.internal_step, 17), 'Position', position);
    end
end
names = fieldnames(cfg.components);
positions = struct('a', [360 90 485 170], 'b', [360 300 485 380], ...
    'c', [610 90 735 170], 'd', [610 300 735 380]);
if startsWith(meta.id, '04')
    positions.c = [170 190 295 270];
    positions.d = [620 190 745 270];
end
for k = 1:numel(names)
    spec = cfg.components.(names{k});
    if ~strcmp(spec.type, 'fmu'), continue; end
    path = [model '/' names{k}];
    add_block('built-in/SubSystem', path, 'Position', positions.(names{k}));
    add_adder_blocks(path, num2str(spec.parameters.Gain, 17));
end
log_index = 0;
for k = 1:numel(cfg.connections)
    connection = cfg.connections(k);
    src = source_path(connection);
    if strcmp(connection.dst_comp, 'log')
        log_index = log_index + 1;
        sink = ['log_' connection.dst_port];
        add_block('simulink/Sinks/To Workspace', [model '/' sink], ...
            'VariableName', ['ref_' connection.dst_port], 'SaveFormat', 'Timeseries', ...
            'SampleTime', num2str(meta.internal_step, 17), 'MaxDataPoints', 'inf', ...
            'Position', [880 45 + log_index*65 1030 75 + log_index*65]);
        add_line(model, src, [sink '/1'], 'autorouting', 'on');
        continue;
    end
    port = 1 + strcmp(connection.dst_port, 'Feedback');
    dst = [connection.dst_comp '/' num2str(port)];
    delayed = isfield(connection, 'delayed') && ~isempty(connection.delayed) && connection.delayed;
    if delayed
        delay = ['explicit_delay_' num2str(k)];
        initial = 0;
        key = matlab.lang.makeValidName([connection.src_comp '.' connection.src_port]);
        if isfield(cfg, 'initial_values') && isfield(cfg.initial_values, key)
            initial = cfg.initial_values.(key);
        end
        add_block('simulink/Discrete/Unit Delay', [model '/' delay], ...
            'SampleTime', num2str(cfg.dt, 17), 'InitialCondition', num2str(initial, 17), ...
            'Position', [240 440 305 480]);
        add_line(model, src, [delay '/1'], 'autorouting', 'on');
        src = [delay '/1'];
    end
    add_line(model, src, dst, 'autorouting', 'on');
end
set_param(model, 'SolverType', 'Fixed-step', 'Solver', 'FixedStepDiscrete', ...
    'FixedStep', num2str(meta.internal_step, 17), ...
    'StartTime', num2str(cfg.start, 17), 'StopTime', num2str(cfg.stop, 17), ...
    'RelTol', '1e-10', 'AbsTol', '1e-12', 'AlgebraicLoopMsg', 'warning', ...
    'ReturnWorkspaceOutputs', 'on', 'SaveOutput', 'off', 'SaveTime', 'on');
end

function path = source_path(connection)
if strcmp(connection.src_comp, 'source')
    path = ['src_' connection.src_port '/1'];
else
    assert(strcmp(connection.src_port, 'Out'), 'Unexpected adder output port.');
    path = [connection.src_comp '/1'];
end
end
