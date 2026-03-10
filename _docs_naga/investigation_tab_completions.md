# Tab Completions: Formula vs Cask — Gap Analysis & Fix Plan

## Summary

The `azure-cli` **formula** delivers working zsh/bash/fish tab completion automatically at install time.
The `azure-cli` **cask** ships with **no completion support at all**.
This document explains how each path works, what the gap is, and how to fix it using the `gcloud-cli` pattern as a direct precedent.

---

## 1. How the Formula Delivers Completions

The homebrew-core formula (`azure-cli.rb`) calls Homebrew's built-in helper at the end of `install`:

```ruby
generate_completions_from_executable(libexec/"bin/register-python-argcomplete", "az",
                                     base_name: "az", shell_parameter_format: :arg)
```

What this does at install time:

1. Runs `/opt/homebrew/Cellar/azure-cli/<version>/libexec/bin/register-python-argcomplete az --shell zsh` (and similarly for bash/fish).
2. Captures the output — a static completion script.
3. Writes the result to the Homebrew share directory:
   - `$HOMEBREW_PREFIX/share/zsh/site-functions/_az`
   - `$HOMEBREW_PREFIX/share/bash-completion/completions/az`
   - `$HOMEBREW_PREFIX/share/fish/vendor_completions.d/az.fish`

`brew shellenv` already adds `$HOMEBREW_PREFIX/share/zsh/site-functions` to `$FPATH`, so as long as `compinit` has been called the completions are active.

The underlying generator is **argcomplete** (`argcomplete` PyPI package, `register-python-argcomplete` binary). The `az.completion` file in the repo is a bash-specific argcomplete shim — it is **not** the zsh completion file.

### Required compinit note

`brew shellenv` adds site-functions to `$FPATH` but does **not** call `compinit`. Without `compinit`, zsh never activates any completion functions.

Fix (add to `~/.zshrc`):

```zsh
autoload -Uz compinit && compinit
```

---

## 2. How the Cask Currently Works (Gap)

Current `azure-cli.rb` cask:

```ruby
cask "azure-cli" do
  # ...
  binary "bin/az"
  zap trash: "~/.azure"
end
```

- No `zsh_completion`, `bash_completion`, or `fish_completion` stanza.
- The tarball contains only `bin/az` (and supporting Python libs).
- **Result: zero tab completion for cask users**, regardless of `compinit` setup.

The cask cannot run `generate_completions_from_executable` — that is a formula-only DSL method.
Casks must point to **pre-existing files** already present in the installed artifact (tarball, dmg, pkg).

---

## 3. Precedent: Real Casks That Bundle Completions

### gcloud-cli (closest match — tarball-based Python CLI, no .app)

```ruby
bash_completion "google-cloud-sdk/completion.bash.inc", target: "google-cloud-sdk"
zsh_completion  "google-cloud-sdk/completion.zsh.inc",  target: "_google_cloud_sdk"
```

The `.inc` files are shipped **inside the tarball**. The `target:` parameter controls the symlink name placed in Homebrew's share directory.

### orbstack (app bundle, multiple tools)

```ruby
bash_completion "#{appdir}/OrbStack.app/Contents/Resources/completions/bash/orbctl.bash"
fish_completion "#{appdir}/OrbStack.app/Contents/Resources/completions/fish/orbctl.fish"
zsh_completion  "#{appdir}/OrbStack.app/Contents/Resources/completions/zsh/_orb"
zsh_completion  "#{appdir}/OrbStack.app/Contents/Resources/completions/zsh/_orbctl"
```

Stores completions under `Contents/Resources/completions/{bash,fish,zsh}/`.

### docker-desktop (dmg, all three shells)

```ruby
bash_completion "#{appdir}/Docker.app/Contents/Resources/etc/docker.bash-completion"
fish_completion "#{appdir}/Docker.app/Contents/Resources/etc/docker.fish-completion"
zsh_completion  "#{appdir}/Docker.app/Contents/Resources/etc/docker.zsh-completion"
```

### vagrant (pkg installer, embedded gems path)

```ruby
bash_completion "/opt/vagrant/embedded/gems/gems/vagrant-#{version}/contrib/bash/completion.sh", target: "vagrant"
zsh_completion  "/opt/vagrant/embedded/gems/gems/vagrant-#{version}/contrib/zsh/_vagrant"
```

---

## 4. Fix Plan for the azure-cli Cask

### Step 1 — Pre-generate completion files in the release pipeline

Run these commands during the macOS build/packaging step, **after** the virtualenv is assembled but **before** tarball creation:

```bash
# From inside the azure-cli source / virtualenv
az completion -s zsh  > completions/zsh/_az
az completion -s bash > completions/bash/az
az completion -s fish > completions/fish/az.fish
```

> `az completion -s <shell>` is the native azure-cli subcommand.  
> It invokes argcomplete's `register-python-argcomplete` internally and prints the result to stdout.

### Step 2 — Bundle the completions directory in the tarball

The tarball layout should become:

```
azure-cli-<version>-macos-<arch>/
  bin/
    az
  completions/
    zsh/
      _az
    bash/
      az
    fish/
      az.fish
  lib/
    ...
```

### Step 3 — Add stanzas to the cask

```ruby
cask "azure-cli" do
  # ...existing fields...

  binary "bin/az"

  zsh_completion  "completions/zsh/_az"
  bash_completion "completions/bash/az"
  fish_completion "completions/fish/az.fish"

  zap trash: "~/.azure"
end
```

Homebrew will symlink:
- `completions/zsh/_az`   → `$HOMEBREW_PREFIX/share/zsh/site-functions/_az`
- `completions/bash/az`    → `$HOMEBREW_PREFIX/share/bash-completion/completions/az`
- `completions/fish/az.fish` → `$HOMEBREW_PREFIX/share/fish/vendor_completions.d/az.fish`

No post-install script needed. No formula methods needed. Works with standard cask DSL.

---

## 5. Comparison Summary

| Aspect | Formula | Cask (current) | Cask (after fix) |
|---|---|---|---|
| Zsh completion | Auto-generated at install via `generate_completions_from_executable` | None | Pre-generated file in tarball + `zsh_completion` stanza |
| Bash completion | Auto-generated at install | None | Pre-generated file in tarball + `bash_completion` stanza |
| Fish completion | Auto-generated at install | None | Pre-generated file in tarball + `fish_completion` stanza |
| Requires `compinit` in `~/.zshrc` | Yes | N/A | Yes (same as formula) |
| Precedent | — | — | `gcloud-cli`, `orbstack`, `docker-desktop` |

---

## 6. File Paths (this workspace)

| File | Path |
|---|---|
| Current cask | `mycli-app/_scratch_brew/azure-cli.rb` |
| Homebrew-core formula | `homebrew-core/Formula/azure-cli.rb` |
| gcloud-cli reference | `homebrew-cask/Casks/g/gcloud-cli.rb` |
| orbstack reference | `homebrew-cask/Casks/o/orbstack.rb` |
| docker-desktop reference | `homebrew-cask/Casks/d/docker-desktop.rb` |
| vagrant reference | `homebrew-cask/Casks/v/vagrant.rb` |
| Bash argcomplete shim | `azure-cli-pkg-1/az.completion` |
