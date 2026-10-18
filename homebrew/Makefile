# Homebrew management Makefile
MACHINE ?= $(shell cat ../.machine 2>/dev/null)

.PHONY: install install-packages dump

# Install Homebrew from scratch
install:
	bash install.sh

# Install shared packages and the selected machine's additions
install-packages:
	@case "$(MACHINE)" in machine-1|machine-2) ;; *) echo 'Set ../.machine or pass MACHINE=machine-1 or MACHINE=machine-2' >&2; exit 1 ;; esac
	brew bundle install --file="Brewfile.$(MACHINE)"

# Snapshot installed packages without overwriting the curated Brewfile
dump:
	brew bundle dump --force --file=Brewfile.snapshot.local
