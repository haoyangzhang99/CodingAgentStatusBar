#import <Foundation/Foundation.h>
#include <Python.h>

// Native executable for "OpenCode Status Bar.app". install.sh compiles it with
// PYTHON_EXECUTABLE set to the project's virtual environment interpreter.
int main(int argc, char **argv) {
    @autoreleasepool {
        // Keep the native executable inside the bundle while Python runs in-process.
        // exec-ing a bare interpreter loses the app identity needed by status items.
        BOOL check = argc > 1 && strcmp(argv[1], "--check") == 0;
        if (!check) {
            NSString *dir = [NSHomeDirectory() stringByAppendingPathComponent:
                @"Library/Logs/OpenCodeStatusBar"];
            [NSFileManager.defaultManager createDirectoryAtPath:dir
                withIntermediateDirectories:YES attributes:nil error:nil];
            NSString *log = [dir stringByAppendingPathComponent:@"launcher.log"];
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
            NSString *identifier = NSBundle.mainBundle.bundleIdentifier ?: @"(not in an app bundle)";
            printf("App identity: %s\n", identifier.UTF8String);
            fflush(stdout);
            result = PyRun_SimpleString("from opencode_status_bar.app import main\nprint('Python imports: OK', flush=True)");
            Py_FinalizeEx();
        } else {
            result = PyRun_SimpleString("from opencode_status_bar.app import main\nmain()");
        }
        return result == 0 ? 0 : 1;
    }
}
