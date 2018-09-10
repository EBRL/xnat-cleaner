# Xnat Cleaner
The purpose of this package is to update the Cutting lab's data on XNAT so that it remains consistent and appropriately named. This allows assessors to be run on the data in a timely fashion, and promots analyses by alerting users to inappropriate data
        
## Usage
To run a subject through the cleaner, do the following:

```
from cleaner import XnatSubject
x = XnatSubject('LD4001_v1', print_summary=True)
```

This instantiates a new subject and runs the following:

1. `self.get_metadata()`: Retrieves subject information from Xnat and dumps it into `x.meta`, `x.session_df` and `x.scan_df`.
1. `self.match_scan_types()`: Checks for scans that might be eligible for renaming.
1. `self.run_test_functions()`: Tests for common errors, such as duplicate scans or incomplete scans.
1. `self.print_summary()`: prints a summary of the scan to the screen. 

To actually edit the XNAT objects...

* `x.update_unusable_scan_types()` to rename "incomplete scans".
* `x.update_scan_types(overwrite=True)` to apply renames to scan types.


#### Sources of error
- All subjects should match the RegEx pattern: '[A-Z]{2}\d{4}_v[A-Z0-9]' (e.g. LD4001_v1)

#### Future improvements
- Check if the scan quality is consistent with expectatinos (e.g. same amount of frames), file size, etc.
