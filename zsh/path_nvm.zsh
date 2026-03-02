export NVM_DIR="$HOME/.nvm"

_load_nvm() {
  unfunction nvm node npm npx yarn 2>/dev/null
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"
}

for cmd in nvm node npm npx yarn; do
  eval "${cmd}() { _load_nvm; ${cmd} \"\$@\" }"
done
