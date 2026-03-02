FPATH="$HOMEBREW_PREFIX/share/zsh-completions:$FPATH"
fpath=($HOME/.docker/completions $fpath)

autoload -Uz compinit
if [[ -n ${ZDOTDIR:-$HOME}/.zcompdump(#qN.mh+24) ]]; then
  compinit
else
  compinit -C
fi
