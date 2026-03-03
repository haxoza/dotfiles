FPATH="$HOMEBREW_PREFIX/share/zsh-completions:$FPATH"
fpath=($HOME/.docker/completions $fpath)

autoload -Uz compinit
if [[ -f ${ZDOTDIR:-$HOME}/.zcompdump && -z ${ZDOTDIR:-$HOME}/.zcompdump(#qN.mh+24) ]]; then
  compinit -C
else
  compinit
fi
