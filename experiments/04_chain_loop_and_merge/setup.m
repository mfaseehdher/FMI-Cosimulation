% Prepare missing SLX models, export FMUs and simulate this MATLAB reference.
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
addpath(fullfile(root, 'matlab'));
prepare_models('04_chain_loop_and_merge');
build_all('04_chain_loop_and_merge');
