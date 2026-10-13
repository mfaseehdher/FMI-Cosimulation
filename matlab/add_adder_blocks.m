function add_adder_blocks(system, gain)
% This subsystem is feedthrough only: no solver, state, or internal feedback.
add_block('simulink/Sources/In1', [system '/Bias'], 'Position', [35 40 65 60]);
add_block('simulink/Sources/In1', [system '/Feedback'], ...
    'Port', '2', 'Position', [35 125 65 145]);
add_block('simulink/Math Operations/Gain', [system '/Gain'], ...
    'Gain', gain, 'Position', [115 110 180 160]);
add_block('simulink/Math Operations/Sum', [system '/Add'], ...
    'Inputs', '++', 'Position', [235 45 265 115]);
add_block('simulink/Sinks/Out1', [system '/Out'], 'Position', [320 70 350 90]);
add_line(system, 'Bias/1', 'Add/1', 'autorouting', 'on');
add_line(system, 'Feedback/1', 'Gain/1', 'autorouting', 'on');
add_line(system, 'Gain/1', 'Add/2', 'autorouting', 'on');
add_line(system, 'Add/1', 'Out/1', 'autorouting', 'on');
end
