#import <Foundation/Foundation.h>
#include <Python.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        // Keep the native executable inside the bundle while Python runs in-process.
        // exec-ing a bare interpreter loses the app identity needed by status items.
        BOOL check = argc > 1 && strcmp(argv[1], "--check") == 0;
        if (!check) {
            NSString *log = [NSHomeDirectory() stringByAppendingPathComponent:
                @"Library/Logs/OpenCodeMonitor/launcher.log"];
            freopen(log.fileSystemRepresentation, "a", stderr);
        }

        PyConfig config;
        PyConfig_InitPythonConfig(&config);
        config.use_environment = 0;
        config.parse_argv = 0;
        PyStatus status = PyConfig_SetBytesString(&config, &config.program_name, PYTHON_EXECUTABLE);
        if (!PyStatus_Exception(status))
            status = PyConfig_SetBytesString(&config, &config.executable, PYTHON_EXECUTABLE);
        if (!PyStatus_Exception(status))
            status = Py_InitializeFromConfig(&config);
        PyConfig_Clear(&config);
        if (PyStatus_Exception(status))
            Py_ExitStatusException(status);

        int result;
        if (check) {
            printf("App identity: %s\n", NSBundle.mainBundle.bundleIdentifier.UTF8String);
            result = PyRun_SimpleString("from opencode_monitor.app import main\nprint('Monitor imports successfully')");
            Py_FinalizeEx();
        } else {
            result = PyRun_SimpleString("from opencode_monitor.app import main\nmain()");
        }
        return result == 0 ? 0 : 1;
    }
}
