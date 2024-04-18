if type brew &>/dev/null; then
    FPATH=$(brew --prefix)/share/zsh-completions:$FPATH
    
    autoload -Uz compin
    compinit
fi

# You may also need to force rebuild `zcompdump`:
#
#    rm -f ~/.zcompdump; compinit
#
# Additionally, if you receive "zsh compinit: insecure directories" warnings when attempting
# to load these completions, you may need to run these commands:
#
#    chmod go-w '$HOMEBREW_PREFIX/share'
#    chmod -R go-w '$HOMEBREW_PREFIX/share/zsh'
