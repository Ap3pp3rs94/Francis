#include "FrancisPresenceStageActor.h"

#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "FrancisPresence.h"
#include "FrancisPresenceBridge.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

AFrancisPresenceStageActor::AFrancisPresenceStageActor()
{
    PrimaryActorTick.bCanEverTick = true;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    CoreSphere = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CoreSphere"));
    CoreSphere->SetupAttachment(Root);
    CoreSphere->SetRelativeLocation(FVector(0.0, 0.0, 230.0));
    CoreSphere->SetRelativeScale3D(FVector(1.25));
    CoreSphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CoreSphere->SetCastShadow(true);

    InnerSphere = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("InnerSphere"));
    InnerSphere->SetupAttachment(CoreSphere);
    InnerSphere->SetRelativeScale3D(FVector(0.72));
    InnerSphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    Floor = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Floor"));
    Floor->SetupAttachment(Root);
    Floor->SetRelativeLocation(FVector(0.0, 0.0, -20.0));
    Floor->SetRelativeScale3D(FVector(16.0, 16.0, 0.1));
    Floor->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    Backdrop = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Backdrop"));
    Backdrop->SetupAttachment(Root);
    Backdrop->SetRelativeLocation(FVector(0.0, 500.0, 260.0));
    Backdrop->SetRelativeScale3D(FVector(16.0, 0.1, 7.0));
    Backdrop->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereAsset(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeAsset(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> LitShapeMaterial(
        TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")
    );
    if (SphereAsset.Succeeded())
    {
        CoreSphere->SetStaticMesh(SphereAsset.Object);
        InnerSphere->SetStaticMesh(SphereAsset.Object);
    }
    if (CubeAsset.Succeeded())
    {
        Floor->SetStaticMesh(CubeAsset.Object);
        Backdrop->SetStaticMesh(CubeAsset.Object);
    }
    if (LitShapeMaterial.Succeeded())
    {
        CoreSphere->SetMaterial(0, LitShapeMaterial.Object);
        InnerSphere->SetMaterial(0, LitShapeMaterial.Object);
        Floor->SetMaterial(0, LitShapeMaterial.Object);
        Backdrop->SetMaterial(0, LitShapeMaterial.Object);
    }

    RingOne = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RingOne"));
    RingOne->SetupAttachment(Root);
    RingOne->SetRelativeLocation(FVector(0.0, 0.0, 230.0));
    RingOne->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RingOne->SetCastShadow(false);
    RingTwo = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RingTwo"));
    RingTwo->SetupAttachment(Root);
    RingTwo->SetRelativeLocation(FVector(0.0, 0.0, 230.0));
    RingTwo->SetRelativeRotation(FRotator(62.0, 0.0, 18.0));
    RingTwo->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RingTwo->SetCastShadow(false);
    RingThree = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RingThree"));
    RingThree->SetupAttachment(Root);
    RingThree->SetRelativeLocation(FVector(0.0, 0.0, 230.0));
    RingThree->SetRelativeRotation(FRotator(-48.0, 22.0, 0.0));
    RingThree->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RingThree->SetCastShadow(false);
    if (LitShapeMaterial.Succeeded())
    {
        RingOne->SetMaterial(0, LitShapeMaterial.Object);
        RingTwo->SetMaterial(0, LitShapeMaterial.Object);
        RingThree->SetMaterial(0, LitShapeMaterial.Object);
    }

    AmbientParticles = CreateDefaultSubobject<UNiagaraComponent>(TEXT("AmbientParticles"));
    AmbientParticles->SetupAttachment(Root);
    AmbientParticles->SetRelativeLocation(FVector(0.0, 0.0, 195.0));
    AmbientParticles->SetRelativeScale3D(FVector(0.35));
    static ConstructorHelpers::FObjectFinder<UNiagaraSystem> NiagaraAsset(
        TEXT("/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight")
    );
    if (NiagaraAsset.Succeeded())
    {
        AmbientParticles->SetAsset(NiagaraAsset.Object);
        AmbientParticles->SetAutoActivate(true);
    }

    CoreLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("CoreLight"));
    CoreLight->SetupAttachment(Root);
    CoreLight->SetRelativeLocation(FVector(0.0, -40.0, 230.0));
    CoreLight->SetIntensityUnits(ELightUnits::Candelas);
    CoreLight->SetIntensity(320.0f);
    CoreLight->SetAttenuationRadius(520.0f);
    CoreLight->SetUseInverseSquaredFalloff(true);

    RimLightLeft = CreateDefaultSubobject<URectLightComponent>(TEXT("RimLightLeft"));
    RimLightLeft->SetupAttachment(Root);
    RimLightLeft->SetRelativeLocation(FVector(-320.0, -180.0, 320.0));
    RimLightLeft->SetRelativeRotation(FRotator(-10.0, 25.0, 0.0));
    RimLightLeft->SetIntensity(220.0f);
    RimLightLeft->SetSourceWidth(220.0f);
    RimLightLeft->SetSourceHeight(360.0f);

    RimLightRight = CreateDefaultSubobject<URectLightComponent>(TEXT("RimLightRight"));
    RimLightRight->SetupAttachment(Root);
    RimLightRight->SetRelativeLocation(FVector(320.0, -100.0, 190.0));
    RimLightRight->SetRelativeRotation(FRotator(0.0, -35.0, 0.0));
    RimLightRight->SetIntensity(160.0f);
    RimLightRight->SetSourceWidth(180.0f);
    RimLightRight->SetSourceHeight(380.0f);

    KeyLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("KeyLight"));
    KeyLight->SetupAttachment(Root);
    KeyLight->SetRelativeRotation(FRotator(-42.0, -35.0, 0.0));
    KeyLight->SetIntensity(0.65f);

    SkyLight = CreateDefaultSubobject<USkyLightComponent>(TEXT("SkyLight"));
    SkyLight->SetupAttachment(Root);
    SkyLight->SetIntensity(0.18f);
    SkyLight->SetMobility(EComponentMobility::Movable);

    PostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("PostProcess"));
    PostProcess->SetupAttachment(Root);
    PostProcess->bUnbound = true;
    PostProcess->Settings.bOverride_BloomIntensity = true;
    PostProcess->Settings.BloomIntensity = 0.15f;
    PostProcess->Settings.bOverride_AutoExposureMinBrightness = true;
    PostProcess->Settings.bOverride_AutoExposureMaxBrightness = true;
    PostProcess->Settings.AutoExposureMinBrightness = 0.8f;
    PostProcess->Settings.AutoExposureMaxBrightness = 0.8f;
    PostProcess->Settings.bOverride_VignetteIntensity = true;
    PostProcess->Settings.VignetteIntensity = 0.2f;

    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(Root);
    Camera->SetRelativeLocation(FVector(-40.0, -1500.0, 320.0));
    Camera->SetFieldOfView(52.0f);
    Camera->SetAutoActivate(true);
}

void AFrancisPresenceStageActor::BeginPlay()
{
    Super::BeginPlay();
    Camera->SetRelativeRotation((FVector(0.0, 0.0, 220.0) - Camera->GetRelativeLocation()).Rotation());
    BuildTorus(RingOne, 145.0f, 2.8f);
    BuildTorus(RingTwo, 180.0f, 2.0f);
    BuildTorus(RingThree, 215.0f, 1.4f);
    Floor->SetVectorParameterValueOnMaterials(TEXT("Color"), FVector(0.006f, 0.012f, 0.022f));
    Backdrop->SetVectorParameterValueOnMaterials(TEXT("Color"), FVector(0.01f, 0.018f, 0.035f));
    if (APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        Controller->SetViewTarget(this);
    }
    ApplyPresenceState();
}

void AFrancisPresenceStageActor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    Elapsed += DeltaSeconds;
    RingOne->AddLocalRotation(FRotator(0.0, 17.0f * DeltaSeconds, 5.0f * DeltaSeconds));
    RingTwo->AddLocalRotation(FRotator(7.0f * DeltaSeconds, -11.0f * DeltaSeconds, 0.0));
    RingThree->AddLocalRotation(FRotator(-4.0f * DeltaSeconds, 8.0f * DeltaSeconds, 6.0f * DeltaSeconds));
    const float Pulse = 1.0f + FMath::Sin(Elapsed * 1.45f) * 0.025f;
    CoreSphere->SetRelativeScale3D(FVector(1.25f * Pulse));
    CoreLight->SetIntensity(240.0f + (FMath::Sin(Elapsed * 1.8f) + 1.0f) * 80.0f);

    if (FFrancisPresenceModule::IsAvailable())
    {
        if (FFrancisPresenceBridge* Bridge = FFrancisPresenceModule::Get().GetBridge())
        {
            const FFrancisPresenceViewModel Current = Bridge->GetViewModel();
            if (Current.Revision != AppliedRevision)
            {
                AppliedRevision = Current.Revision;
                ApplyPresenceState();
                if (!Current.EnvelopeId.IsEmpty() && Current.Sequence > 0)
                {
                    Bridge->MarkRendered(Current.EnvelopeId, Current.Sequence);
                }
            }
        }
    }
}

void AFrancisPresenceStageActor::BuildTorus(
    UProceduralMeshComponent* Mesh,
    float MajorRadius,
    float MinorRadius
) const
{
    constexpr int32 MajorSegments = 96;
    constexpr int32 MinorSegments = 12;
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FLinearColor> Colors;
    TArray<FProcMeshTangent> Tangents;
    Vertices.Reserve(MajorSegments * MinorSegments);
    Normals.Reserve(MajorSegments * MinorSegments);
    UVs.Reserve(MajorSegments * MinorSegments);
    Colors.Reserve(MajorSegments * MinorSegments);
    Tangents.Reserve(MajorSegments * MinorSegments);

    for (int32 Major = 0; Major < MajorSegments; ++Major)
    {
        const float U = 2.0f * PI * Major / MajorSegments;
        const FVector Center(MajorRadius * FMath::Cos(U), MajorRadius * FMath::Sin(U), 0.0f);
        for (int32 Minor = 0; Minor < MinorSegments; ++Minor)
        {
            const float V = 2.0f * PI * Minor / MinorSegments;
            const FVector Normal(
                FMath::Cos(U) * FMath::Cos(V),
                FMath::Sin(U) * FMath::Cos(V),
                FMath::Sin(V)
            );
            Vertices.Add(Center + Normal * MinorRadius);
            Normals.Add(Normal);
            UVs.Add(FVector2D(static_cast<float>(Major) / MajorSegments, static_cast<float>(Minor) / MinorSegments));
            Colors.Add(StateColor);
            Tangents.Add(FProcMeshTangent(-FMath::Sin(U), FMath::Cos(U), 0.0f));
        }
    }
    for (int32 Major = 0; Major < MajorSegments; ++Major)
    {
        for (int32 Minor = 0; Minor < MinorSegments; ++Minor)
        {
            const int32 Current = Major * MinorSegments + Minor;
            const int32 NextMajor = ((Major + 1) % MajorSegments) * MinorSegments + Minor;
            const int32 NextMinor = Major * MinorSegments + (Minor + 1) % MinorSegments;
            const int32 NextBoth = ((Major + 1) % MajorSegments) * MinorSegments + (Minor + 1) % MinorSegments;
            Triangles.Append({Current, NextMajor, NextBoth, Current, NextBoth, NextMinor});
        }
    }
    Mesh->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
}

void AFrancisPresenceStageActor::ApplyPresenceState()
{
    FFrancisPresenceViewModel Current;
    if (FFrancisPresenceModule::IsAvailable() && FFrancisPresenceModule::Get().GetBridge())
    {
        Current = FFrancisPresenceModule::Get().GetBridge()->GetViewModel();
    }
    const FString Combined = (Current.PresenceState + TEXT(" ") + Current.SemanticState + TEXT(" ") + Current.IncidentPressure).ToLower();
    if (Combined.Contains(TEXT("fault")) || Combined.Contains(TEXT("error")) || Combined.Contains(TEXT("panic")))
    {
        StateColor = FLinearColor(0.95f, 0.19f, 0.12f, 1.0f);
    }
    else if (Combined.Contains(TEXT("attention")) || Combined.Contains(TEXT("blocked")) || Combined.Contains(TEXT("warning")))
    {
        StateColor = FLinearColor(0.94f, 0.42f, 0.04f, 1.0f);
    }
    else if (Combined.Contains(TEXT("handoff")) || Combined.Contains(TEXT("review")))
    {
        StateColor = FLinearColor(0.23f, 0.43f, 0.96f, 1.0f);
    }
    else
    {
        StateColor = FLinearColor(0.06f, 0.72f, 0.68f, 1.0f);
    }
    CoreLight->SetLightColor(FLinearColor(0.55f, 0.72f, 1.0f));
    RimLightLeft->SetLightColor(StateColor * 0.35f + FLinearColor(0.08f, 0.12f, 0.22f, 0.0f));
    RimLightRight->SetLightColor(FLinearColor(0.28f, 0.38f, 1.0f));
    const FVector CoreVector(StateColor.R, StateColor.G, StateColor.B);
    CoreSphere->SetVectorParameterValueOnMaterials(TEXT("Color"), CoreVector);
    InnerSphere->SetVectorParameterValueOnMaterials(TEXT("Color"), FVector(0.72f, 0.88f, 0.96f));
    RingOne->SetVectorParameterValueOnMaterials(TEXT("Color"), CoreVector);
    RingTwo->SetVectorParameterValueOnMaterials(TEXT("Color"), CoreVector * 0.65f);
    RingThree->SetVectorParameterValueOnMaterials(TEXT("Color"), FVector(0.22f, 0.38f, 1.0f));
    AmbientParticles->SetVariableLinearColor(TEXT("User.Color"), StateColor);
}
