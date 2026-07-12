using UnrealBuildTool;

public class FrancisPresence : ModuleRules
{
    public FrancisPresence(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        bUseUnity = true;
        MinSourceFilesForUnityBuildOverride = 2;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "EnhancedInput"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "ApplicationCore",
            "Json",
            "JsonUtilities",
            "Niagara",
            "NiagaraCore",
            "ProceduralMeshComponent",
            "Projects",
            "RenderCore",
            "RHI",
            "Slate",
            "SlateCore",
            "UMG"
        });

        PublicSystemLibraries.Add("bcrypt.lib");
    }
}
