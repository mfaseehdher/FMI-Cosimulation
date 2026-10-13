% Prepare missing SLX models, export FMUs and simulate this MATLAB reference.
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
addpath(fullfile(root, 'matlab'));
prepare_models('03_negative_feedback');
build_all('03_negative_feedback');
