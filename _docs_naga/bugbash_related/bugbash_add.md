-- current state
brew info azure-cli
az upgrade to see if any one has old version.
brew uninstall azure-cli
brew reinstall azure-cli


-- new
brew reinstall --cask azure-cli
brew info --cask azure-cli   
az upgrade 
brew upgrade --cask azure-cli
brew uninstall --cask azure-cli


