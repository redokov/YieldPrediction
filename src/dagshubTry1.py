from dagshub.streaming import DagsHubFilesystem, install_hooks

# Install hooks for DagsHub-aware file operations
install_hooks(repo_url="https://dagshub.com/DagsHub-Datasets/sentinel-3-dataset")

# Initialize the DagsHubFilesystem
fs = DagsHubFilesystem(repo_url="https://dagshub.com/DagsHub-Datasets/sentinel-3-dataset")



# Example usage of DagsHubFilesystem to list files in a directory
directory_path = "s3:/sentinel-cogs/sentinel-s2-l2a-cogs/38/T/LP/2024/1/S2A_38TLP_20240102_0_L2A"  # Replace with your actual directory path
files = fs.listdir(directory_path)

# Print the list of files
print("Files in directory:", files)

# Example of opening a file using DagsHubFilesystem
file_path = "s3:/sentinel-cogs/sentinel-s2-l2a-cogs/38/T/LP/2024/1/S2A_38TLP_20240102_0_L2A/S2A_38TLP_20240102_0_L2A.json"  # Replace with your actual file path
with fs.open(file_path, 'r') as file:
    content = file.read()
    print("Content of the file:", content)