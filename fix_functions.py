import os

os.system('git show HEAD~1:api/index.html > temp_old.html')

with open('temp_old.html', 'r', encoding='utf-8') as f:
    old_content = f.read()

start_str = 'function render2StepVoicePicker()'
end_str = 'function onVoiceSelected()'

start_idx = old_content.find(start_str)
end_idx = old_content.find(end_str, start_idx)

functions_to_restore = old_content[start_idx:end_idx]

with open('api/index.html', 'r', encoding='utf-8') as f:
    new_content = f.read()

update_func_end = new_content.find('function onVoiceSelected()')
final_content = new_content[:update_func_end] + functions_to_restore + '\n    ' + new_content[update_func_end:]

with open('api/index.html', 'w', encoding='utf-8') as f:
    f.write(final_content)
