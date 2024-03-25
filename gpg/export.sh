#!/usr/bin/env sh

gpg --export -a "Przemek Lewandowski" > public.gpg
gpg --export-secret-keys -a "Przemek Lewandowski" > private.gpg


