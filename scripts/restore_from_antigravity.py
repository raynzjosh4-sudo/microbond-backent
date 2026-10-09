import os
import json
import shutil
import urllib.parse

appdata = os.environ.get('APPDATA')
history_path = os.path.join(appdata, 'Antigravity IDE', 'User', 'History')
target_prefix = "c:/users/raynz/onedrive/desktop/project/microbond/microbond-backend/app"

recovered_count = 0

if os.path.exists(history_path):
    for folder in os.listdir(history_path):
        folder_path = os.path.join(history_path, folder)
        entries_file = os.path.join(folder_path, 'entries.json')
        
        if os.path.exists(entries_file):
            try:
                with open(entries_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                resource = data.get('resource', '')
                if resource.startswith('file:///'):
                    parsed_path = urllib.parse.unquote(resource[8:])
                    
                    if parsed_path.lower().startswith(target_prefix):
                        entries = data.get('entries', [])
                        if entries:
                            latest_entry = sorted(entries, key=lambda x: x.get('timestamp', 0))[-1]
                            snapshot_id = latest_entry.get('id')
                            snapshot_path = os.path.join(folder_path, snapshot_id)
                            
                            dest_path = os.path.normpath(parsed_path)
                            
                            if os.path.exists(snapshot_path):
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                shutil.copy2(snapshot_path, dest_path)
                                print(f"Restored {dest_path}")
                                recovered_count += 1
            except Exception as e:
                print(f"Error processing {entries_file}: {e}")

print(f"Total files restored from Antigravity IDE Local History: {recovered_count}")
