alias copyssh="pbcopy < $HOME/.ssh/id_rsa.pub"
alias reloadcli="source $HOME/.zshrc"
alias dotfiles="cd $DOTFILES"
alias projects="cd ~/dev/projects"
alias docker-composer="docker-compose"

alias tableflip="echo '(╯°□°）╯︵ ┻━┻' | pbcopy"

# Claude remote workstation mode (lid-closed, stays awake)
station-on() {
  sudo pmset -a disablesleep 1
  echo "Mac will stay awake with lid closed. Lock screen still active."
}

station-off() {
  sudo pmset -a disablesleep 0
  echo "Normal sleep behavior restored."
}

