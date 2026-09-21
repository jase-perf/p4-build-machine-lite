// Put this in a folder called Editor anywhere under Assets/ (Unity only runs
// -executeMethod on scripts that live in an Editor folder).
//
// build.bat runs it with: Unity.exe -batchmode -quit -executeMethod BuildScript.Build
// It builds the scenes from File > Build Profiles > Scene List into BUILD_OUTPUT.
// A test build is a Development Build, which keeps Unity's error reporting and the
// profiler. A release build is what players get: no development extras.
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class BuildScript
{
    public static void Build()
    {
        var output = Environment.GetEnvironmentVariable("BUILD_OUTPUT");
        if (string.IsNullOrEmpty(output))
            output = Path.Combine(Directory.GetCurrentDirectory(), "build");
        var release = Environment.GetEnvironmentVariable("BUILD_KIND") == "release";

        var options = new BuildPlayerOptions
        {
            scenes = EditorBuildSettings.scenes.Where(scene => scene.enabled)
                                              .Select(scene => scene.path).ToArray(),
            locationPathName = Path.Combine(output, "MyGame.exe"),
            target = BuildTarget.StandaloneWindows64,
            options = release ? BuildOptions.None : BuildOptions.Development,
        };
        if (options.scenes.Length == 0)
            Debug.LogWarning("No scenes are enabled in Build Profiles > Scene List.");

        var summary = BuildPipeline.BuildPlayer(options).summary;
        Debug.Log($"{(release ? "Release" : "Test")} build {summary.result}, " +
                  $"{summary.totalErrors} error(s), {summary.totalSize} bytes");
        // Unity exits 0 from -quit even after a failed build, so say so ourselves.
        EditorApplication.Exit(summary.result == BuildResult.Succeeded ? 0 : 1);
    }
}
