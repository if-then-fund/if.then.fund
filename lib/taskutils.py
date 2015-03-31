# Utilities for long-running tasks.
###################################

# The three exclusive_process routines were created by Josh originally for
# Mail-in-a-Box, where he dedicated it to the public domain using CC0.

def exclusive_process(name):
    # Ensure that this process, globally named `name`, does not execute
    # multiple times concurrently.

    import os, os.path, sys, atexit
    if os.access('/var/run', os.W_OK):
        # process is probably run as root
        piddir = '/var/run'
    else:
        # process is probably a non-root user
        piddir = '/tmp'
    pidfile = os.path.join(piddir, '%s.pid' % name)
    mypid = os.getpid()

    # Attempt to get a lock on ourself so that the concurrency check
    # itself is not executed in parallel.
    with open(__file__, 'r+') as flock:
        # Try to get a lock. This blocks until a lock is acquired. The
        # lock is held until the flock file is closed at the end of the
        # with block.
        os.lockf(flock.fileno(), os.F_LOCK, 0)

        # While we have a lock, look at the pid file. First attempt
        # to write our pid to a pidfile if no file already exists there.
        try:
            with open(pidfile, 'x') as f:
                # Successfully opened a new file. Since the file is new
                # there is no concurrent process. Write our pid.
                f.write(str(mypid))

                # When this process exits, remove the pid file.
                atexit.register(clear_my_pid, pidfile)
                return

        except FileExistsError:
            # The pid file already exixts, but it may contain a stale
            # pid of a terminated process.
            with open(pidfile, 'r+') as f:
                # Read the pid in the file.
                existing_pid = None
                try:
                    existing_pid = int(f.read().strip())
                except ValueError:
                    pass # No valid integer in the file.

                # Check if the pid in it is valid. If it is, there is
		# already a process running. Quit.
                if existing_pid:
                    if is_pid_valid(existing_pid):
                        print("Another %s process is already running (pid %d)." % (name, existing_pid), file=sys.stderr)
                        sys.exit(1)

                # This pid is stale. Write over it with our pid.
                f.seek(0)
                f.write(str(mypid))
                f.truncate()

                # When this process exits, remove the pid file.
                atexit.register(clear_my_pid, pidfile)
 
def clear_my_pid(pidfile):
    import os
    os.unlink(pidfile)

def is_pid_valid(pid):
    """Checks whether a pid is a valid process ID of a currently running process."""
    # adapted from http://stackoverflow.com/questions/568271/how-to-check-if-there-exists-a-process-with-a-given-pid
    import os, errno
    if pid <= 0: raise ValueError('Invalid PID.')
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH: # No such process
            return False
        elif err.errno == errno.EPERM: # Not permitted to send signal
            return True
        else: # EINVAL
            raise
    else:
        return True

