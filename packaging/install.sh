#!/bin/sh
# tinyTouch Batch 0 installer, macOS Apple Silicon only.
#
# Served from https://alpacaengineer.ing/tinytouch/batch-0/install.sh and run as:
#   curl -fsSL https://alpacaengineer.ing/tinytouch/batch-0/install.sh | sh
#
# release_sha256 pins the binary produced by packaging/build-standalone-macos.sh.
# Update both values together whenever a new binary is uploaded.
set -eu

release_url='https://alpacaengineer.ing/tinytouch/batch-0/tinytouch'
release_sha256='9f21b29f82bc3d4829621b2e7f1314d2165e06111424a55cec05b75d044e7a4a'
install_dir="${TINYTOUCH_INSTALL_DIR:-$HOME/.local/bin}"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT HUP INT TERM

if [ "$(uname -s)" != 'Darwin' ]; then
  echo 'tinyTouch setup requires macOS.' >&2
  exit 1
fi

if [ "$(uname -m)" != 'arm64' ]; then
  echo 'tinyTouch Batch 0 requires an Apple Silicon Mac.' >&2
  exit 1
fi

echo 'Downloading tinyTouch…'
curl -fsSL "$release_url" -o "$work_dir/tinytouch"
actual_sha256="$(shasum -a 256 "$work_dir/tinytouch" | awk '{print $1}')"
if [ "$actual_sha256" != "$release_sha256" ]; then
  echo 'Download checksum did not match. Stopping.' >&2
  exit 1
fi

mkdir -p "$install_dir"
cp "$work_dir/tinytouch" "$install_dir/tinytouch"
chmod 755 "$install_dir/tinytouch"
xattr -d com.apple.quarantine "$install_dir/tinytouch" 2>/dev/null || true

echo "Installed tinyTouch to $install_dir/tinytouch"

# Add ~/.local/bin to PATH. Login shells read .zprofile/.bash_profile, but shells
# started without -l (editor terminals, some multiplexers) only read .zshrc/.bashrc,
# so write both. The guard keeps the line idempotent if it ends up sourced twice.
path_line='case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac'
case "${SHELL:-/bin/zsh}" in
  */bash) profiles="$HOME/.bash_profile $HOME/.bashrc"; restart_command='exec bash -l' ;;
  *) profiles="$HOME/.zprofile $HOME/.zshrc"; restart_command='exec zsh -l' ;;
esac

path_added=''
if [ "$install_dir" = "$HOME/.local/bin" ]; then
  for profile in $profiles; do
    if ! grep -Fq '.local/bin' "$profile" 2>/dev/null; then
      printf '\n# tinyTouch CLI\n%s\n' "$path_line" >> "$profile"
      echo "Added tinyTouch to PATH in $profile"
      path_added='yes'
    fi
  done
fi

# This script runs in a child process, so it cannot change PATH in the terminal that
# started it. Tell the user how to pick up the change without opening a new window.
echo
if [ -n "$path_added" ]; then
  echo 'To use tinytouch in this terminal, reload your shell:'
  echo "    $restart_command"
  echo
fi
echo 'Then run: tinytouch setup'
echo "Or run it now without reloading: $install_dir/tinytouch setup"
