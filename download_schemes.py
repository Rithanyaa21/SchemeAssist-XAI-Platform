from huggingface_hub import snapshot_download

snapshot_download(
    "shrijayan/gov_myscheme",
    repo_type="dataset",
    local_dir="./gov_myscheme"
)

print("Dataset downloaded successfully.")