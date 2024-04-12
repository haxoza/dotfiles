# this required since macOS 14, see https://github.com/lra/mackup/issues/1924

backup:
	mackup backup --force
	mackup uninstall --force

restore:
	mackup restore
	mackup uninstall --force
