install brew 


brew untap naga-nandyala/mycli-app
brew tap naga-nandyala/mycli-app

brew install --cask  azure-cli-v3

brew install --cask naga-nandyala/mycli-app/azure-cli-v3
 



### offline install
mkdir -p /tmp/azure-cli-offline/install
tar -xzf /tmp/azure-cli-offline/azure-cli-2.77.0-macos-arm64-nopython-signed-notarized.tar.gz -C /tmp/azure-cli-offline/install
ls -la /tmp/azure-cli-offline/install/

which pyenv && pyenv versions 2>/dev/null || echo "pyenv not installed"

AZ_PYTHON="$HOME/.pyenv/versions/3.13.1/bin/python3" /tmp/azure-cli-offline/install/bin/az version 2>&1



## quarantine
find ~/Library/Caches/Homebrew/downloads -name "*azure-cli*" -delete
