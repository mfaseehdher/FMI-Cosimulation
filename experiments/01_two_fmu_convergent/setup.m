% Prepare missing SLX models, export FMUs and simulate this MATLAB reference.
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
addpath(fullfile(root, 'matlab'));
prepare_models('01_two_fmu_convergent');
build_all('01_two_fmu_convergent');
