// Keep this in Assets/Editor: Unity only runs -executeMethod on Editor scripts.
// build.bat and build.sh call it to build the scenes in Build Profiles into BUILD_OUTPUT,
// for the computer it runs on: a Development Build for test builds, a normal one for release.
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
        var (target, file) = Application.platform switch
        {
            RuntimePlatform.OSXEditor => (BuildTarget.StandaloneOSX, "MyGame.app"),
            RuntimePlatform.LinuxEditor => (BuildTarget.StandaloneLinux64, "MyGame.x86_64"),
            _ => (BuildTarget.StandaloneWindows64, "MyGame.exe"),
        };

        var options = new BuildPlayerOptions
        {
            scenes = EditorBuildSettings.scenes.Where(scene => scene.enabled)
                                              .Select(scene => scene.path).ToArray(),
            locationPathName = Path.Combine(output, file),
            target = target,
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
