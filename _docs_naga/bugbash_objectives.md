# High level objectives


## current state 

- check current state of azure-cli installation (via homebrew-core) and arhitecture of macos.
- check the location of azure-cli installation. (az --version).
- capture existing list of extensions & configs.
- az login to one of azclienttools tenants.
- if none.. insall azdo extension and list azclienttools org project list.
- uninstall azure-cli
- verify ~/.azure folder (it should be retained along with configs./extensions.)
  
## new install approach (brew)

- tap into custom homebrew tap.
- verify the local tap and formula.
- perform installation using brew install --cask azure-cli
- verify location of installs.
- verify signatures
- run few az commands.
- check old extensions and run them.


## broker based authentication.

- check company portal s/w and version.
- az login should automatically invoke broker.
- set config as false.. it should now default to brower
- set coinfig back to true.. is should invoke broker.
- uninstall broker but config = tru.. it should default to browser


## offline approach 

- uninsall existing azure-cli (both homebrew-core and homebrew-cask variants)
- download and untar it in temp locatoin.
- verify location of installs.
- verify signatures
- az --versin should fail
- install python from non homebrew location.
- set AZ_PYTHON
- run az --version.
- check old extensions and run them.
- uninstall the custom python,
- cleanup temp.



## uninstall and install current azure-cli
  