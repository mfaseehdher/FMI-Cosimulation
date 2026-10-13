% Prepare missing SLX models, export FMUs and simulate this MATLAB reference.
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
addpath(fullfile(root, 'matlab'));
prepare_models('06_unit_gain_inconsistent');
build_all('06_unit_gain_inconsistent');
