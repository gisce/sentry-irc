# sentry-irc
A plugin for [Sentry](https://www.getsentry.com/) that logs errors to an IRC room.
## Installation
`$ pip install sentry-irc`

Add `sentry_irc` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = (
    #...
    'sentry',
    'sentry_irc',
)
```
