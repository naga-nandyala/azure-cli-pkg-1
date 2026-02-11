# Dependency Superset (Full Outer Join)
Each table includes all setup.py packages plus any requirements-only packages.
Mismatch Summary is only populated when there is a mismatch.

| Package | azure-cli (setup) | azure-cli-core (setup) | azure-cli-telemetry (setup) | req-darwin | req-windows | req-linux | Mismatch Summary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PyGithub | PyGithub~=1.38 | - | - | PyGithub==1.55 | PyGithub==1.55 | PyGithub==1.55 | 🟡 align version pins |
| PyJWT | - | PyJWT>=2.1.0 | - | PyJWT==2.10.1 | PyJWT==2.10.1 | PyJWT==2.10.1 | 🟡 align version pins |
| PyNaCl | PyNaCl~=1.6.2 | - | - | PyNaCl==1.6.2 | PyNaCl==1.6.2 | PyNaCl==1.6.2 | 🟡 align version pins |
| PySocks | - | - | - | PySocks==1.7.1 | PySocks==1.7.1 | PySocks==1.7.1 | 🟡 not in any setup.py |
| antlr4-python3-runtime | antlr4-python3-runtime~=4.13.1 | - | - | antlr4-python3-runtime==4.13.1 | antlr4-python3-runtime==4.13.1 | antlr4-python3-runtime==4.13.1 | 🟡 align version pins |
| applicationinsights | - | - | applicationinsights>=0.11.1,<0.12 | applicationinsights==0.11.9 | applicationinsights==0.11.9 | applicationinsights==0.11.9 | 🟡 align version pins |
| argcomplete | - | argcomplete~=3.5.2 | - | argcomplete==3.5.2 | argcomplete==3.5.2 | argcomplete==3.5.2 | 🟡 align version pins |
| asn1crypto | - | - | - | asn1crypto==0.24.0 | asn1crypto==0.24.0 | asn1crypto==0.24.0 | 🟡 not in any setup.py |
| azure-ai-projects | azure-ai-projects~=1.0.0 | - | - | - | - | - | 🔴 missing requirements |
| azure-appconfiguration | azure-appconfiguration~=1.7.2 | - | - | azure-appconfiguration==1.7.2 | azure-appconfiguration==1.7.2 | azure-appconfiguration==1.7.2 | 🟡 align version pins |
| azure-batch | azure-batch==15.0.0b1 | - | - | azure-batch==15.0.0b1 | azure-batch==15.0.0b1 | azure-batch==15.0.0b1 | ✅ no issues |
| azure-cli | - | - | - | azure-cli==2.83.0 | azure-cli==2.83.0 | azure-cli==2.83.0 | 🟡 not in any setup.py |
| azure-cli-core | azure-cli-core==2.83.0 | - | - | azure-cli-core==2.83.0 | azure-cli-core==2.83.0 | azure-cli-core==2.83.0 | ✅ no issues |
| azure-cli-telemetry | - | azure-cli-telemetry==1.1.0.* | - | azure-cli-telemetry==1.1.0 | azure-cli-telemetry==1.1.0 | azure-cli-telemetry==1.1.0 | 🟡 align version pins |
| azure-common | - | - | - | azure-common==1.1.22 | azure-common==1.1.22 | azure-common==1.1.22 | 🟡 not in any setup.py |
| azure-core | - | azure-core~=1.38.0 | - | azure-core==1.38.0 | azure-core==1.38.0 | azure-core==1.38.0 | 🟡 align version pins |
| azure-cosmos | azure-cosmos~=3.0,>=3.0.2 | - | - | azure-cosmos==3.2.0 | azure-cosmos==3.2.0 | azure-cosmos==3.2.0 | 🟡 align version pins |
| azure-data-tables | azure-data-tables==12.4.0 | - | - | azure-data-tables==12.4.0 | azure-data-tables==12.4.0 | azure-data-tables==12.4.0 | ✅ no issues |
| azure-datalake-store | azure-datalake-store~=1.0.1 | - | - | azure-datalake-store==1.0.1 | azure-datalake-store==1.0.1 | azure-datalake-store==1.0.1 | 🟡 align version pins |
| azure-keyvault-administration | azure-keyvault-administration==4.4.0 | - | - | azure-keyvault-administration==4.4.0 | azure-keyvault-administration==4.4.0 | azure-keyvault-administration==4.4.0 | ✅ no issues |
| azure-keyvault-certificates | azure-keyvault-certificates==4.7.0 | - | - | azure-keyvault-certificates==4.7.0 | azure-keyvault-certificates==4.7.0 | azure-keyvault-certificates==4.7.0 | ✅ no issues |
| azure-keyvault-keys | azure-keyvault-keys==4.11.0 | - | - | azure-keyvault-keys==4.11.0 | azure-keyvault-keys==4.11.0 | azure-keyvault-keys==4.11.0 | ✅ no issues |
| azure-keyvault-secrets | azure-keyvault-secrets==4.7.0 | - | - | azure-keyvault-secrets==4.7.0 | azure-keyvault-secrets==4.7.0 | azure-keyvault-secrets==4.7.0 | ✅ no issues |
| azure-keyvault-securitydomain | azure-keyvault-securitydomain==1.0.0b1 | - | - | azure-keyvault-securitydomain==1.0.0b1 | azure-keyvault-securitydomain==1.0.0b1 | azure-keyvault-securitydomain==1.0.0b1 | ✅ no issues |
| azure-mgmt-advisor | azure-mgmt-advisor==9.0.0 | - | - | azure-mgmt-advisor==9.0.0 | azure-mgmt-advisor==9.0.0 | azure-mgmt-advisor==9.0.0 | ✅ no issues |
| azure-mgmt-apimanagement | azure-mgmt-apimanagement==4.0.0 | - | - | azure-mgmt-apimanagement==4.0.0 | azure-mgmt-apimanagement==4.0.0 | azure-mgmt-apimanagement==4.0.0 | ✅ no issues |
| azure-mgmt-appconfiguration | azure-mgmt-appconfiguration==5.0.0 | - | - | azure-mgmt-appconfiguration==5.0.0 | azure-mgmt-appconfiguration==5.0.0 | azure-mgmt-appconfiguration==5.0.0 | ✅ no issues |
| azure-mgmt-appcontainers | azure-mgmt-appcontainers==2.0.0 | - | - | azure-mgmt-appcontainers==2.0.0 | azure-mgmt-appcontainers==2.0.0 | azure-mgmt-appcontainers==2.0.0 | ✅ no issues |
| azure-mgmt-applicationinsights | azure-mgmt-applicationinsights~=1.0.0 | - | - | azure-mgmt-applicationinsights==1.0.0 | azure-mgmt-applicationinsights==1.0.0 | azure-mgmt-applicationinsights==1.0.0 | 🟡 align version pins |
| azure-mgmt-authorization | azure-mgmt-authorization==5.0.0b1 | - | - | azure-mgmt-authorization==5.0.0b1 | azure-mgmt-authorization==5.0.0b1 | azure-mgmt-authorization==5.0.0b1 | ✅ no issues |
| azure-mgmt-batch | azure-mgmt-batch~=17.3.0 | - | - | azure-mgmt-batch==17.3.0 | azure-mgmt-batch==17.3.0 | azure-mgmt-batch==17.3.0 | 🟡 align version pins |
| azure-mgmt-batchai | azure-mgmt-batchai==7.0.0b1 | - | - | azure-mgmt-batchai==7.0.0b1 | azure-mgmt-batchai==7.0.0b1 | azure-mgmt-batchai==7.0.0b1 | ✅ no issues |
| azure-mgmt-billing | azure-mgmt-billing==6.0.0 | - | - | azure-mgmt-billing==6.0.0 | azure-mgmt-billing==6.0.0 | azure-mgmt-billing==6.0.0 | ✅ no issues |
| azure-mgmt-botservice | azure-mgmt-botservice~=2.0.0b3 | - | - | azure-mgmt-botservice==2.0.0b3 | azure-mgmt-botservice==2.0.0b3 | azure-mgmt-botservice==2.0.0b3 | 🟡 align version pins |
| azure-mgmt-cdn | azure-mgmt-cdn==12.0.0 | - | - | azure-mgmt-cdn==12.0.0 | azure-mgmt-cdn==12.0.0 | azure-mgmt-cdn==12.0.0 | ✅ no issues |
| azure-mgmt-cognitiveservices | azure-mgmt-cognitiveservices~=14.1.0 | - | - | azure-mgmt-cognitiveservices==14.1.0 | azure-mgmt-cognitiveservices==14.1.0 | azure-mgmt-cognitiveservices==14.1.0 | 🟡 align version pins |
| azure-mgmt-compute | azure-mgmt-compute~=34.1.0 | - | - | azure-mgmt-compute==34.1.0 | azure-mgmt-compute==34.1.0 | azure-mgmt-compute==34.1.0 | 🟡 align version pins |
| azure-mgmt-containerinstance | azure-mgmt-containerinstance==10.2.0b1 | - | - | azure-mgmt-containerinstance==10.2.0b1 | azure-mgmt-containerinstance==10.2.0b1 | azure-mgmt-containerinstance==10.2.0b1 | ✅ no issues |
| azure-mgmt-containerregistry | azure-mgmt-containerregistry==14.1.0b1 | - | - | azure-mgmt-containerregistry==14.1.0b1 | azure-mgmt-containerregistry==14.1.0b1 | azure-mgmt-containerregistry==14.1.0b1 | ✅ no issues |
| azure-mgmt-containerservice | azure-mgmt-containerservice~=40.2.0 | - | - | azure-mgmt-containerservice==40.2.0 | azure-mgmt-containerservice==40.2.0 | azure-mgmt-containerservice==40.2.0 | 🟡 align version pins |
| azure-mgmt-core | - | azure-mgmt-core>=1.2.0,<2 | - | azure-mgmt-core==1.6.0 | azure-mgmt-core==1.6.0 | azure-mgmt-core==1.6.0 | 🟡 align version pins |
| azure-mgmt-cosmosdb | azure-mgmt-cosmosdb==9.9.0 | - | - | azure-mgmt-cosmosdb==9.9.0 | azure-mgmt-cosmosdb==9.9.0 | azure-mgmt-cosmosdb==9.9.0 | ✅ no issues |
| azure-mgmt-datalake-nspkg | - | - | - | azure-mgmt-datalake-nspkg==3.0.1 | azure-mgmt-datalake-nspkg==3.0.1 | azure-mgmt-datalake-nspkg==3.0.1 | 🟡 not in any setup.py |
| azure-mgmt-datalake-store | azure-mgmt-datalake-store~=1.1.0b1 | - | - | azure-mgmt-datalake-store==1.1.0b1 | azure-mgmt-datalake-store==1.1.0b1 | azure-mgmt-datalake-store==1.1.0b1 | 🟡 align version pins |
| azure-mgmt-datamigration | azure-mgmt-datamigration~=10.0.0 | - | - | azure-mgmt-datamigration==10.0.0 | azure-mgmt-datamigration==10.0.0 | azure-mgmt-datamigration==10.0.0 | 🟡 align version pins |
| azure-mgmt-eventgrid | azure-mgmt-eventgrid==10.2.0b2 | - | - | azure-mgmt-eventgrid==10.2.0b2 | azure-mgmt-eventgrid==10.2.0b2 | azure-mgmt-eventgrid==10.2.0b2 | ✅ no issues |
| azure-mgmt-eventhub | azure-mgmt-eventhub~=12.0.0b1 | - | - | azure-mgmt-eventhub==12.0.0b1 | azure-mgmt-eventhub==12.0.0b1 | azure-mgmt-eventhub==12.0.0b1 | 🟡 align version pins |
| azure-mgmt-extendedlocation | azure-mgmt-extendedlocation==1.0.0b2 | - | - | azure-mgmt-extendedlocation==1.0.0b2 | azure-mgmt-extendedlocation==1.0.0b2 | azure-mgmt-extendedlocation==1.0.0b2 | ✅ no issues |
| azure-mgmt-hdinsight | azure-mgmt-hdinsight==9.1.0b2 | - | - | azure-mgmt-hdinsight==9.1.0b2 | azure-mgmt-hdinsight==9.1.0b2 | azure-mgmt-hdinsight==9.1.0b2 | ✅ no issues |
| azure-mgmt-imagebuilder | azure-mgmt-imagebuilder~=1.3.0 | - | - | azure-mgmt-imagebuilder==1.3.0 | azure-mgmt-imagebuilder==1.3.0 | azure-mgmt-imagebuilder==1.3.0 | 🟡 align version pins |
| azure-mgmt-iotcentral | azure-mgmt-iotcentral~=10.0.0b1 | - | - | azure-mgmt-iotcentral==10.0.0b1 | azure-mgmt-iotcentral==10.0.0b1 | azure-mgmt-iotcentral==10.0.0b1 | 🟡 align version pins |
| azure-mgmt-iothub | azure-mgmt-iothub==5.0.0b1 | - | - | azure-mgmt-iothub==5.0.0b1 | azure-mgmt-iothub==5.0.0b1 | azure-mgmt-iothub==5.0.0b1 | ✅ no issues |
| azure-mgmt-iothubprovisioningservices | azure-mgmt-iothubprovisioningservices==1.1.0 | - | - | azure-mgmt-iothubprovisioningservices==1.1.0 | azure-mgmt-iothubprovisioningservices==1.1.0 | azure-mgmt-iothubprovisioningservices==1.1.0 | ✅ no issues |
| azure-mgmt-keyvault | azure-mgmt-keyvault==13.0.0 | - | - | azure-mgmt-keyvault==13.0.0 | azure-mgmt-keyvault==13.0.0 | azure-mgmt-keyvault==13.0.0 | ✅ no issues |
| azure-mgmt-loganalytics | azure-mgmt-loganalytics==13.0.0b4 | - | - | azure-mgmt-loganalytics==13.0.0b4 | azure-mgmt-loganalytics==13.0.0b4 | azure-mgmt-loganalytics==13.0.0b4 | ✅ no issues |
| azure-mgmt-managementgroups | azure-mgmt-managementgroups~=1.0.0 | - | - | azure-mgmt-managementgroups==1.0.0 | azure-mgmt-managementgroups==1.0.0 | azure-mgmt-managementgroups==1.0.0 | 🟡 align version pins |
| azure-mgmt-maps | azure-mgmt-maps~=2.0.0 | - | - | azure-mgmt-maps==2.0.0 | azure-mgmt-maps==2.0.0 | azure-mgmt-maps==2.0.0 | 🟡 align version pins |
| azure-mgmt-marketplaceordering | azure-mgmt-marketplaceordering==1.1.0 | - | - | azure-mgmt-marketplaceordering==1.1.0 | azure-mgmt-marketplaceordering==1.1.0 | azure-mgmt-marketplaceordering==1.1.0 | ✅ no issues |
| azure-mgmt-media | azure-mgmt-media~=9.0 | - | - | azure-mgmt-media==9.0.0 | azure-mgmt-media==9.0.0 | azure-mgmt-media==9.0.0 | 🟡 align version pins |
| azure-mgmt-monitor | azure-mgmt-monitor~=7.0.0b1 | - | - | azure-mgmt-monitor==7.0.0b1 | azure-mgmt-monitor==7.0.0b1 | azure-mgmt-monitor==7.0.0b1 | 🟡 align version pins |
| azure-mgmt-msi | azure-mgmt-msi~=7.1.0 | - | - | azure-mgmt-msi==7.1.0 | azure-mgmt-msi==7.1.0 | azure-mgmt-msi==7.1.0 | 🟡 align version pins |
| azure-mgmt-mysqlflexibleservers | azure-mgmt-mysqlflexibleservers==1.1.0b2 | - | - | azure-mgmt-mysqlflexibleservers==1.1.0b2 | azure-mgmt-mysqlflexibleservers==1.1.0b2 | azure-mgmt-mysqlflexibleservers==1.1.0b2 | ✅ no issues |
| azure-mgmt-netapp | azure-mgmt-netapp~=10.1.0 | - | - | azure-mgmt-netapp==10.1.0 | azure-mgmt-netapp==10.1.0 | azure-mgmt-netapp==10.1.0 | 🟡 align version pins |
| azure-mgmt-policyinsights | azure-mgmt-policyinsights==1.1.0b4 | - | - | azure-mgmt-policyinsights==1.1.0b4 | azure-mgmt-policyinsights==1.1.0b4 | azure-mgmt-policyinsights==1.1.0b4 | ✅ no issues |
| azure-mgmt-postgresqlflexibleservers | azure-mgmt-postgresqlflexibleservers==2.0.0 | - | - | azure-mgmt-postgresqlflexibleservers==2.0.0 | azure-mgmt-postgresqlflexibleservers==2.0.0 | azure-mgmt-postgresqlflexibleservers==2.0.0 | ✅ no issues |
| azure-mgmt-privatedns | azure-mgmt-privatedns~=1.0.0 | - | - | azure-mgmt-privatedns==1.0.0 | azure-mgmt-privatedns==1.0.0 | azure-mgmt-privatedns==1.0.0 | 🟡 align version pins |
| azure-mgmt-rdbms | azure-mgmt-rdbms==10.2.0b17 | - | - | azure-mgmt-rdbms==10.2.0b17 | azure-mgmt-rdbms==10.2.0b17 | azure-mgmt-rdbms==10.2.0b17 | ✅ no issues |
| azure-mgmt-recoveryservices | azure-mgmt-recoveryservices~=4.0.0 | - | - | azure-mgmt-recoveryservices==4.0.0 | azure-mgmt-recoveryservices==4.0.0 | azure-mgmt-recoveryservices==4.0.0 | 🟡 align version pins |
| azure-mgmt-recoveryservicesbackup | azure-mgmt-recoveryservicesbackup~=9.2.0 | - | - | azure-mgmt-recoveryservicesbackup==9.2.0 | azure-mgmt-recoveryservicesbackup==9.2.0 | azure-mgmt-recoveryservicesbackup==9.2.0 | 🟡 align version pins |
| azure-mgmt-redhatopenshift | azure-mgmt-redhatopenshift~=1.5.0 | - | - | azure-mgmt-redhatopenshift==1.5.0 | azure-mgmt-redhatopenshift==1.5.0 | azure-mgmt-redhatopenshift==1.5.0 | 🟡 align version pins |
| azure-mgmt-redis | azure-mgmt-redis~=14.5.0 | - | - | azure-mgmt-redis==14.5.0 | azure-mgmt-redis==14.5.0 | azure-mgmt-redis==14.5.0 | 🟡 align version pins |
| azure-mgmt-resource | azure-mgmt-resource==23.3.0 | - | - | azure-mgmt-resource==23.3.0 | azure-mgmt-resource==23.3.0 | azure-mgmt-resource==23.3.0 | ✅ no issues |
| azure-mgmt-resource-deployments | azure-mgmt-resource-deployments==1.0.0b1 | - | - | azure-mgmt-resource-deployments==1.0.0b1 | azure-mgmt-resource-deployments==1.0.0b1 | azure-mgmt-resource-deployments==1.0.0b1 | ✅ no issues |
| azure-mgmt-resource-deploymentscripts | azure-mgmt-resource-deploymentscripts==1.0.0b1 | - | - | azure-mgmt-resource-deploymentscripts==1.0.0b1 | azure-mgmt-resource-deploymentscripts==1.0.0b1 | azure-mgmt-resource-deploymentscripts==1.0.0b1 | ✅ no issues |
| azure-mgmt-resource-deploymentstacks | azure-mgmt-resource-deploymentstacks==1.0.0b1 | - | - | azure-mgmt-resource-deploymentstacks==1.0.0b1 | azure-mgmt-resource-deploymentstacks==1.0.0b1 | azure-mgmt-resource-deploymentstacks==1.0.0b1 | ✅ no issues |
| azure-mgmt-resource-templatespecs | azure-mgmt-resource-templatespecs==1.0.0b1 | - | - | azure-mgmt-resource-templatespecs==1.0.0b1 | azure-mgmt-resource-templatespecs==1.0.0b1 | azure-mgmt-resource-templatespecs==1.0.0b1 | ✅ no issues |
| azure-mgmt-search | azure-mgmt-search~=9.0 | - | - | azure-mgmt-search==9.0.0 | azure-mgmt-search==9.0.0 | azure-mgmt-search==9.0.0 | 🟡 align version pins |
| azure-mgmt-security | azure-mgmt-security==6.0.0 | - | - | azure-mgmt-security==6.0.0 | azure-mgmt-security==6.0.0 | azure-mgmt-security==6.0.0 | ✅ no issues |
| azure-mgmt-servicebus | azure-mgmt-servicebus~=10.0.0b1 | - | - | azure-mgmt-servicebus==10.0.0b1 | azure-mgmt-servicebus==10.0.0b1 | azure-mgmt-servicebus==10.0.0b1 | 🟡 align version pins |
| azure-mgmt-servicefabric | azure-mgmt-servicefabric~=2.1.0 | - | - | azure-mgmt-servicefabric==2.1.0 | azure-mgmt-servicefabric==2.1.0 | azure-mgmt-servicefabric==2.1.0 | 🟡 align version pins |
| azure-mgmt-servicefabricmanagedclusters | azure-mgmt-servicefabricmanagedclusters==2.1.0b1 | - | - | azure-mgmt-servicefabricmanagedclusters==2.1.0b1 | azure-mgmt-servicefabricmanagedclusters==2.1.0b1 | azure-mgmt-servicefabricmanagedclusters==2.1.0b1 | ✅ no issues |
| azure-mgmt-servicelinker | azure-mgmt-servicelinker==1.2.0b3 | - | - | azure-mgmt-servicelinker==1.2.0b3 | azure-mgmt-servicelinker==1.2.0b3 | azure-mgmt-servicelinker==1.2.0b3 | ✅ no issues |
| azure-mgmt-signalr | azure-mgmt-signalr==2.0.0b2 | - | - | azure-mgmt-signalr==2.0.0b2 | azure-mgmt-signalr==2.0.0b2 | azure-mgmt-signalr==2.0.0b2 | ✅ no issues |
| azure-mgmt-sql | azure-mgmt-sql==4.0.0b22 | - | - | azure-mgmt-sql==4.0.0b22 | azure-mgmt-sql==4.0.0b22 | azure-mgmt-sql==4.0.0b22 | ✅ no issues |
| azure-mgmt-sqlvirtualmachine | azure-mgmt-sqlvirtualmachine==1.0.0b5 | - | - | azure-mgmt-sqlvirtualmachine==1.0.0b5 | azure-mgmt-sqlvirtualmachine==1.0.0b5 | azure-mgmt-sqlvirtualmachine==1.0.0b5 | ✅ no issues |
| azure-mgmt-storage | azure-mgmt-storage==24.0.0 | - | - | azure-mgmt-storage==24.0.0 | azure-mgmt-storage==24.0.0 | azure-mgmt-storage==24.0.0 | ✅ no issues |
| azure-mgmt-synapse | azure-mgmt-synapse==2.1.0b5 | - | - | azure-mgmt-synapse==2.1.0b5 | azure-mgmt-synapse==2.1.0b5 | azure-mgmt-synapse==2.1.0b5 | ✅ no issues |
| azure-mgmt-trafficmanager | azure-mgmt-trafficmanager~=1.0.0 | - | - | azure-mgmt-trafficmanager==1.0.0 | azure-mgmt-trafficmanager==1.0.0 | azure-mgmt-trafficmanager==1.0.0 | 🟡 align version pins |
| azure-mgmt-web | azure-mgmt-web==9.0.0 | - | - | azure-mgmt-web==9.0.0 | azure-mgmt-web==9.0.0 | azure-mgmt-web==9.0.0 | ✅ no issues |
| azure-monitor-query | azure-monitor-query==1.2.0 | - | - | azure-monitor-query==1.2.0 | azure-monitor-query==1.2.0 | azure-monitor-query==1.2.0 | ✅ no issues |
| azure-nspkg | - | - | - | azure-nspkg==3.0.2 | azure-nspkg==3.0.2 | azure-nspkg==3.0.2 | 🟡 not in any setup.py |
| azure-storage-blob | azure-storage-blob==12.28.0b1 | - | - | azure-storage-blob==12.28.0b1 | azure-storage-blob==12.28.0b1 | azure-storage-blob==12.28.0b1 | ✅ no issues |
| azure-storage-common | azure-storage-common~=1.4 | - | - | azure-storage-common==1.4.2 | azure-storage-common==1.4.2 | azure-storage-common==1.4.2 | 🟡 align version pins |
| azure-storage-file-datalake | azure-storage-file-datalake==12.23.0b1 | - | - | azure-storage-file-datalake==12.23.0b1 | azure-storage-file-datalake==12.23.0b1 | azure-storage-file-datalake==12.23.0b1 | ✅ no issues |
| azure-storage-file-share | azure-storage-file-share==12.24.0b1 | - | - | azure-storage-file-share==12.24.0b1 | azure-storage-file-share==12.24.0b1 | azure-storage-file-share==12.24.0b1 | ✅ no issues |
| azure-storage-queue | azure-storage-queue==12.15.0b1 | - | - | azure-storage-queue==12.15.0b1 | azure-storage-queue==12.15.0b1 | azure-storage-queue==12.15.0b1 | ✅ no issues |
| azure-synapse-accesscontrol | azure-synapse-accesscontrol~=0.5.0 | - | - | azure-synapse-accesscontrol==0.5.0 | azure-synapse-accesscontrol==0.5.0 | azure-synapse-accesscontrol==0.5.0 | 🟡 align version pins |
| azure-synapse-artifacts | azure-synapse-artifacts~=0.21.0 | - | - | azure-synapse-artifacts==0.21.0 | azure-synapse-artifacts==0.21.0 | azure-synapse-artifacts==0.21.0 | 🟡 align version pins |
| azure-synapse-managedprivateendpoints | azure-synapse-managedprivateendpoints~=0.4.0 | - | - | azure-synapse-managedprivateendpoints==0.4.0 | azure-synapse-managedprivateendpoints==0.4.0 | azure-synapse-managedprivateendpoints==0.4.0 | 🟡 align version pins |
| azure-synapse-spark | azure-synapse-spark~=0.7.0 | - | - | azure-synapse-spark==0.7.0 | azure-synapse-spark==0.7.0 | azure-synapse-spark==0.7.0 | 🟡 align version pins |
| bcrypt | - | - | - | bcrypt==3.2.0 | bcrypt==3.2.0 | bcrypt==3.2.0 | 🟡 not in any setup.py |
| certifi | - | - | - | certifi==2024.7.4 | certifi==2024.7.4 | certifi==2024.7.4 | 🟡 not in any setup.py |
| cffi | - | - | - | cffi==2.0.0 | cffi==2.0.0 | cffi==2.0.0 | 🟡 not in any setup.py |
| chardet | chardet~=5.2.0 | - | - | chardet==5.2.0 | chardet==5.2.0 | chardet==5.2.0 | 🟡 align version pins |
| colorama | colorama~=0.4.4 | - | - | colorama==0.4.6 | colorama==0.4.6 | colorama==0.4.6 | 🟡 align version pins |
| cryptography | - | cryptography | - | cryptography==44.0.1 | cryptography==44.0.1 | cryptography==44.0.1 | 🟡 align version pins |
| distro | distro; sys_platform == "linux" | distro; sys_platform == "linux" | - | - | - | distro==1.6.0 | 🟡 align version pins; 🔴 missing requirements |
| fabric | fabric~=3.2.2 | - | - | fabric==3.2.2 | fabric==3.2.2 | fabric==3.2.2 | 🟡 align version pins |
| humanfriendly | - | humanfriendly~=10.0 | - | humanfriendly==10.0 | humanfriendly==10.0 | humanfriendly==10.0 | 🟡 align version pins |
| idna | - | - | - | idna==3.7 | idna==3.7 | idna==3.7 | 🟡 not in any setup.py |
| invoke | - | - | - | invoke==2.2.0 | invoke==2.2.0 | invoke==2.2.0 | 🟡 not in any setup.py |
| isodate | - | - | - | isodate==0.6.1 | isodate==0.6.1 | isodate==0.6.1 | 🟡 not in any setup.py |
| javaproperties | javaproperties~=0.5.1 | - | - | javaproperties==0.5.1 | javaproperties==0.5.1 | javaproperties==0.5.1 | 🟡 align version pins |
| jmespath | - | jmespath | - | jmespath==0.9.5 | jmespath==0.9.5 | jmespath==0.9.5 | 🟡 align version pins |
| jsondiff | jsondiff~=2.0.0 | - | - | jsondiff==2.0.0 | jsondiff==2.0.0 | jsondiff==2.0.0 | 🟡 align version pins |
| knack | - | knack~=0.11.0 | - | knack==0.11.0 | knack==0.11.0 | knack==0.11.0 | 🟡 align version pins |
| microsoft-security-utilities-secret-masker | - | microsoft-security-utilities-secret-masker~=1.0.0b4 | - | - | - | - | 🔴 missing requirements |
| msal | - | msal==1.35.0b1; sys_platform != "win32" | - | msal==1.35.0b1 | - | msal==1.35.0b1 | 🟡 align version pins; 🔴 missing requirements |
| msal-extensions | - | msal-extensions==1.2.0 | - | msal-extensions==1.2.0 | msal-extensions==1.2.0 | msal-extensions==1.2.0 | ✅ no issues |
| msal[broker] | - | msal[broker]==1.35.0b1; sys_platform == "win32" | - | - | msal[broker]==1.35.0b1 | - | 🟡 align version pins; 🔴 missing requirements |
| msrest | - | - | - | msrest==0.7.1 | msrest==0.7.1 | msrest==0.7.1 | 🟡 not in any setup.py |
| oauthlib | - | - | - | oauthlib==3.2.2 | oauthlib==3.2.2 | oauthlib==3.2.2 | 🟡 not in any setup.py |
| packaging | packaging>=20.9 | packaging>=20.9 | - | packaging==25.0 | packaging==25.0 | packaging==25.0 | 🟡 align version pins |
| paramiko | paramiko>=2.0.8,<4.0.0 | - | - | paramiko==3.5.0 | paramiko==3.5.0 | paramiko==3.5.0 | 🟡 align version pins |
| pbr | - | - | - | pbr==5.3.1 | pbr==5.3.1 | pbr==5.3.1 | 🟡 not in any setup.py |
| pkginfo | - | pkginfo>=1.5.0.1 | - | pkginfo==1.8.2 | pkginfo==1.8.2 | pkginfo==1.8.2 | 🟡 align version pins |
| portalocker | - | - | portalocker>=1.6,<3 | portalocker==2.3.2 | portalocker==2.3.2 | portalocker==2.3.2 | 🟡 align version pins |
| psutil | - | psutil>=5.9; sys_platform != "cygwin" | - | psutil==6.1.0 | psutil==6.1.0 | psutil==6.1.0 | 🟡 align version pins |
| py-deviceid | - | py-deviceid | - | - | - | - | 🔴 missing requirements |
| pyOpenSSL | - | - | - | pyOpenSSL==25.0.0 | pyOpenSSL==25.0.0 | pyOpenSSL==25.0.0 | 🟡 not in any setup.py |
| pycomposefile | pycomposefile>=0.0.34 | - | - | pycomposefile==0.0.34 | pycomposefile==0.0.34 | pycomposefile==0.0.34 | 🟡 align version pins |
| pymsalruntime | - | - | - | - | pymsalruntime==0.20.2 | - | 🟡 not in any setup.py |
| pyopenssl | - | pyopenssl>=17.1.0 | - | - | - | - | 🔴 missing requirements |
| python-dateutil | - | - | - | python-dateutil==2.8.0 | python-dateutil==2.8.0 | python-dateutil==2.8.0 | 🟡 not in any setup.py |
| pywin32 | - | - | - | - | pywin32==310 | - | 🟡 not in any setup.py |
| requests | - | - | - | requests==2.32.4 | requests==2.32.4 | requests==2.32.4 | 🟡 not in any setup.py |
| requests-oauthlib | - | - | - | requests-oauthlib==1.2.0 | requests-oauthlib==1.2.0 | requests-oauthlib==1.2.0 | 🟡 not in any setup.py |
| requests[socks] | - | requests[socks] | - | - | - | - | 🔴 missing requirements |
| scp | scp~=0.13.2 | - | - | scp==0.13.2 | scp==0.13.2 | scp==0.13.2 | 🟡 align version pins |
| semver | semver~=3.0 | - | - | semver==3.0.4 | semver==3.0.4 | semver==3.0.4 | 🟡 align version pins |
| setuptools | setuptools | - | - | - | - | - | 🔴 missing requirements |
| six | six>=1.10.0 | - | - | six==1.16.0 | six==1.16.0 | six==1.16.0 | 🟡 align version pins |
| sshtunnel | sshtunnel~=0.1.4 | - | - | sshtunnel==0.1.5 | sshtunnel==0.1.5 | sshtunnel==0.1.5 | 🟡 align version pins |
| tabulate | tabulate | - | - | tabulate==0.8.9 | tabulate==0.8.9 | tabulate==0.8.9 | 🟡 align version pins |
| urllib3 | urllib3 | - | - | urllib3==2.6.3 | urllib3==2.6.3 | urllib3==2.6.3 | 🟡 align version pins |
| wcwidth | - | - | - | wcwidth==0.1.7 | wcwidth==0.1.7 | wcwidth==0.1.7 | 🟡 not in any setup.py |
| websocket-client | websocket-client~=1.3.1 | - | - | websocket-client==1.3.1 | websocket-client==1.3.1 | websocket-client==1.3.1 | 🟡 align version pins |
| xmltodict | xmltodict~=0.12 | - | - | xmltodict==0.12.0 | xmltodict==0.12.0 | xmltodict==0.12.0 | 🟡 align version pins |

