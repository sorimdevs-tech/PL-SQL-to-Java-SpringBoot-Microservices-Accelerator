#!/usr/bin/env python3
"""Check what procedures were extracted from the repo."""

import json
import os

metadata_path = r"C:\Users\THIS PC\Documents\plsql_Acc_output\metadata.json" 

if os.path.exists(metadata_path):
    try:
        with open(metadata_path) as f:
            metadata = json.load(f)
            if 'procedures' in metadata:
                print("Sample of extracted procedures:")
                for proc_name in list(metadata['procedures'].keys())[:5]:
                    proc_info = metadata['procedures'][proc_name]
                    print(f'\nProcedure: {proc_name}')
                    print(f'  Body length: {len(proc_info.get("body", ""))}')
                    body = proc_info.get("body", "")
                    print(f'  Body preview: {body[:200]}...')
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"File not found: {metadata_path}")
    print(f"Current metadata files available:")
    os.system(f'dir "C:\\Users\\THIS PC\\Documents\\plsql_Acc_output\\" /s /b | findstr /i metadata')
