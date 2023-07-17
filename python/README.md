# Inventory

This script is designed to collect CPU, memory and disk information from my homelab servers. This is a simple collection
of functions that pull data from either command line tools such as smartctl or from kernel files (/sys) and parses the
output. The intent was to collect this data and push to a Redis cache for display on a custom website.

This script was put together to test the idea and to gain some experience with different tech and is not really a
complete solution... more a set of ideas that are comming together.
