#!/usr/bin/env sh

gpg --import public.gpg
gpg --allow-secret-key-import --import private.gpg

