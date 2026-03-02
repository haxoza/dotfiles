export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

_load_pyenv() {
  unfunction pyenv python python3 pip pip3 2>/dev/null
  eval "$(command pyenv init -)"
  eval "$(command pyenv virtualenv-init -)"
}

for cmd in pyenv python python3 pip pip3; do
  eval "${cmd}() { _load_pyenv; ${cmd} \"\$@\" }"
done
