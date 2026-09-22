// Keep this under Assets/, outside any Editor folder. It does nothing in normal play.
// Started with -smoketest, the game quits after 5 seconds, with exit code 1 if
// anything logged an error, so build.bat can tell a broken build from a good one.
using System;
using System.Collections;
using UnityEngine;

public class SmokeTest : MonoBehaviour
{
    static bool failed;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    static void Begin()
    {
        if (Array.IndexOf(Environment.GetCommandLineArgs(), "-smoketest") < 0) return;
        Application.logMessageReceived += (message, stackTrace, type) =>
        {
            if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert)
                failed = true;
        };
        var runner = new GameObject("SmokeTest").AddComponent<SmokeTest>();
        DontDestroyOnLoad(runner.gameObject);
    }

    IEnumerator Start()
    {
        yield return new WaitForSecondsRealtime(5);
        Debug.Log(failed ? "Smoke test FAILED" : "Smoke test passed");
        Application.Quit(failed ? 1 : 0);
    }
}
