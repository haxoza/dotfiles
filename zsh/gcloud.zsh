_load_gcloud() {
  unfunction gcloud gsutil bq 2>/dev/null
  source "$HOMEBREW_PREFIX/share/google-cloud-sdk/path.zsh.inc"
  source "$HOMEBREW_PREFIX/share/google-cloud-sdk/completion.zsh.inc"
}

for cmd in gcloud gsutil bq; do
  eval "${cmd}() { _load_gcloud; command ${cmd} \"\$@\" }"
done
