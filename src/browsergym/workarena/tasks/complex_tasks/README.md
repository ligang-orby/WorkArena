# Complex Task Dataset

Complex task dataset v1 includes loop, conditional and comparison tasks. 

The golden trace extraction and proto conversion scripts can be found in [scripts](../../../../../scripts) folder under the repo.

## Known issues
* If you see `playwright._impl._errors.TimeoutError: Page.wait_for_function: Timeout 30000ms exceeded.
` you might need to install `playwright==1.44.0`, according to https://github.com/ServiceNow/WorkArena/issues/57#issuecomment-2587490956