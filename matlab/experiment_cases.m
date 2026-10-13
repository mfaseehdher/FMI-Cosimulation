function records = experiment_cases(selected)
% Read each experiment's checked-in configuration and declared outcomes.
if nargin == 0, selected = ''; end
root = fileparts(fileparts(mfilename('fullpath')));
files = dir(fullfile(root, 'experiments', '*', 'config.json'));
records = struct('folder', {}, 'config', {}, 'metadata', {});
for k = 1:numel(files)
    [~, name] = fileparts(files(k).folder);
    if ~isempty(selected) && ~strcmp(name, selected), continue; end
    item.folder = files(k).folder;
    item.config = jsondecode(fileread(fullfile(item.folder, 'config.json')));
    raw = item.config.connections;
    if ~iscell(raw), raw = num2cell(raw); end
    connections = struct('src_comp', {}, 'src_port', {}, 'dst_comp', {}, 'dst_port', {}, 'delayed', {});
    for index = 1:numel(raw)
        link = raw{index};
        connection.src_comp = link.src_comp;
        connection.src_port = link.src_port;
        connection.dst_comp = link.dst_comp;
        connection.dst_port = link.dst_port;
        connection.delayed = isfield(link, 'delayed') && link.delayed;
        connections(end + 1) = connection; %#ok<AGROW>
    end
    item.config.connections = connections;
    item.metadata = jsondecode(fileread(fullfile(item.folder, 'experiment.json')));
    assert(strcmp(name, item.metadata.id), 'Experiment ID does not match its folder.');
    assert(strcmp(item.metadata.reference_alignment, 'stateless_interval_hold'), ...
        'This builder only supports the documented stateless-adder alignment.');
    records(end + 1) = item; %#ok<AGROW>
end
assert(~isempty(records), 'No matching experiments were found.');
end
