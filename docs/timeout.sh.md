Executes a command with a specified timeout. If the timeout is reached before the command finishes or if a handled signal is sent to the instance of this script, a `SIGTERM` is sent. After a while, if the process still does not finish its execution, a `SIGKILL` signal is sent.