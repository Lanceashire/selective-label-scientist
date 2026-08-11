# Known failures / limitations

- Large-file profiling is performed locally by the persistent sidecar and can take proportional disk time; the React renderer remains responsive and receives only bounded metadata.
- The development build still relies on local Python and Node. Their bundled-runtime acceptance gates remain Loops 13–17.
