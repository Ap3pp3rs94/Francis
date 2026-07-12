using UnrealBuildTool;
using System.Collections.Generic;

public class FrancisPresenceEditorTarget : TargetRules
{
    public FrancisPresenceEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        bUseUnityBuild = true;
        bUseAdaptiveUnityBuild = false;
        ExtraModuleNames.Add("FrancisPresence");
    }
}
