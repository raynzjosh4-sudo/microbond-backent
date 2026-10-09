import json
import os
import re

transcript_path = r"C:\Users\raynz\.gemini\antigravity-ide\brain\58b09636-4841-42d7-86fe-38206790a8a9\.system_generated\logs\transcript_full.jsonl"

files_content = {}

if not os.path.exists(transcript_path):
    print("Transcript not found at", transcript_path)
else:
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                step = json.loads(line)
            except:
                continue
                
            if 'tool_calls' in step and step['tool_calls']:
                for tc in step['tool_calls']:
                    func = tc.get('function', {})
                    if func.get('name') == 'default_api:write_to_file':
                        try:
                            args = json.loads(func.get('arguments', '{}'))
                            path = args.get('TargetFile')
                            content = args.get('CodeContent')
                            if path and content and path.endswith('.py'):
                                path = os.path.normpath(path).lower()
                                files_content[path] = content
                        except:
                            pass
            
            if step.get('type') == 'TOOL_RESPONSE':
                content = step.get('content', '')
                if 'File Path: `file:///' in content:
                    path_match = re.search(r'File Path: `file:///(.+?)`', content)
                    if path_match:
                        raw_path = path_match.group(1).replace('/', '\\')
                        raw_path = os.path.normpath(raw_path).lower()
                        if raw_path.endswith('.py'):
                            lines_match = re.search(r'(?:<original_line>\.\s*Please note.*?\n|\n)(\d+:.*)', content, re.DOTALL)
                            if lines_match:
                                raw_lines = lines_match.group(1).split('\n')
                                clean_lines = []
                                for rl in raw_lines:
                                    if re.match(r'^\d+:', rl):
                                        clean_lines.append(rl.split(':', 1)[1][1:])
                                files_content[raw_path] = '\n'.join(clean_lines)

    for path, content in files_content.items():
        if content.strip():
            print(f"Recovering {path}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fw:
                fw.write(content)
    print(f"Recovered {len(files_content)} files from transcript.")
