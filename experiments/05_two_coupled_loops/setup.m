% Prepare missing SLX models, export FMUs and simulate this MATLAB reference.
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
addpath(fullfile(root, 'matlab'));
prepare_models('05_two_coupled_loops');
build_all('05_two_coupled_loops');
