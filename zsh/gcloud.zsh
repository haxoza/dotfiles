_load_gcloud() {
  unfunction gcloud gsutil bq 2>/dev/null
  source "/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.zsh.inc"
  source "/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/completion.zsh.inc"
}

for cmd in gcloud gsutil bq; do
  eval "${cmd}() { _load_gcloud; ${cmd} \"\$@\" }"
done
