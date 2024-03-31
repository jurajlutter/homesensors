# homesensors
A playground for work with various sensors at home.

## homesens - an app to read and display DHT and uRadMon data

Run `homesens.sh -h` for help.

The mendatory options are the ones around --uradmon

### Usage
```
homesens.py [arguments]

Valid arguments are:  [-h|--help] [-l|--list|--list-sensors] |
                      [-s <n>|--sensor=<n>]
                      [-T <leafoid>] [-H <leafoid>]
                      <[-U|--no-uradmon] --uradmon-id=<id> --uradmon-userid=<userid> --uradmon-userkey=<userkey>>

-h|--help                      Show this help
-l|--list|--list-sensors       List sensors detected
-s <n>|--sensor=<n>            Use sensor number "n" (default: 0)
-T <leafoid>                   Use leafoid for temperature reading (default: temperature)
-H <leafoid>                   Use leafoid for humidity reading (default: humidity)

-U|--no-uradmon                Do not query and display uRadMonitor data

If -U or --no-urandom is NOT specified, then the following arguments are MANDATORY:

--uradmon-id=<id>              Specify uRadMon Device ID
--uradmon-userid=<userid>      Specify uRadMon User ID
--uradmon-userkey=<userkey>    Specify uRadMon User Auth Key
--uradmon-api=<apiurl>         Specity uRadMon API URL, default:
                               https://data.uradmonitor.com/api/v1/devices
```
