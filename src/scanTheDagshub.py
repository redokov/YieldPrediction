# scan the dagshub
# into the defined dir in dagshub. Read all the available dirs, read the json
# https://dagshub.com/DagsHub-Datasets/sentinel-2-l2a-cogs-dataset/src/main/s3:/sentinel-cogs/sentinel-s2-l2a-cogs/38/T/LP/2024
# "eo:cloud_cover"
# "s2:unclassified_percentage"
from dagshub.streaming import DagsHubFilesystem
#from dagshub.streaming import install_hooks
import json

def scan_directory(directory):
    
    fs = DagsHubFilesystem(".", repo_url="https://dagshub.com/DagsHub-Datasets/sentinel-3-dataset")

    json_files = []
    
    for entry in fs.scandir(directory):
        if entry.is_file() and entry.name.endswith('.json'):
            json_files.append(entry.path)
        elif entry.is_dir():
            json_files.extend(scan_directory(entry.path))
    return json_files

def read_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_markdown_table(json_data, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('| Filename | JSON Property Name | JSON Property Value |\n')
        f.write('|----------|-------------------|---------------------|\n')
        for file, properties in json_data.items():
            for prop_name, prop_value in properties.items():
                f.write(f'| {file} | {prop_name} | {prop_value} |\n')

def main():
    directory = 's3:/sentinel-cogs/sentinel-s2-l2a-cogs/38/T/LP/2024/1/S2A_38TLP_20240102_0_L2A'  # Укажите путь к вашему каталогу
    output_file = 'out/out.md'
    
    json_files = scan_directory(directory)
    json_data = {}
    
    for json_file in json_files:
        json_content = read_json(json_file)
        limited_properties = {k: v for i, (k, v) in enumerate(json_content.items()) if i < 10}
        json_data[os.path.basename(json_file)] = limited_properties
    
    write_markdown_table(json_data, output_file)
    print(f'Markdown table has been written to {output_file}')

if __name__ == '__main__':
    main()