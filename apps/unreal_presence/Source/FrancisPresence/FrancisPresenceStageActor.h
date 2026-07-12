#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"

#include "FrancisPresenceStageActor.generated.h"

class UCameraComponent;
class UDirectionalLightComponent;
class UNiagaraComponent;
class UPointLightComponent;
class UPostProcessComponent;
class UProceduralMeshComponent;
class URectLightComponent;
class USceneComponent;
class USkyLightComponent;
class UStaticMeshComponent;

UCLASS()
class FRANCISPRESENCE_API AFrancisPresenceStageActor final : public AActor
{
    GENERATED_BODY()

public:
    AFrancisPresenceStageActor();
    virtual void Tick(float DeltaSeconds) override;

protected:
    virtual void BeginPlay() override;

private:
    void BuildTorus(UProceduralMeshComponent* Mesh, float MajorRadius, float MinorRadius) const;
    void ApplyPresenceState();

    UPROPERTY()
    TObjectPtr<USceneComponent> Root;

    UPROPERTY()
    TObjectPtr<UStaticMeshComponent> CoreSphere;

    UPROPERTY()
    TObjectPtr<UStaticMeshComponent> InnerSphere;

    UPROPERTY()
    TObjectPtr<UStaticMeshComponent> Floor;

    UPROPERTY()
    TObjectPtr<UStaticMeshComponent> Backdrop;

    UPROPERTY()
    TObjectPtr<UProceduralMeshComponent> RingOne;

    UPROPERTY()
    TObjectPtr<UProceduralMeshComponent> RingTwo;

    UPROPERTY()
    TObjectPtr<UProceduralMeshComponent> RingThree;

    UPROPERTY()
    TObjectPtr<UNiagaraComponent> AmbientParticles;

    UPROPERTY()
    TObjectPtr<UPointLightComponent> CoreLight;

    UPROPERTY()
    TObjectPtr<URectLightComponent> RimLightLeft;

    UPROPERTY()
    TObjectPtr<URectLightComponent> RimLightRight;

    UPROPERTY()
    TObjectPtr<UDirectionalLightComponent> KeyLight;

    UPROPERTY()
    TObjectPtr<USkyLightComponent> SkyLight;

    UPROPERTY()
    TObjectPtr<UPostProcessComponent> PostProcess;

    UPROPERTY()
    TObjectPtr<UCameraComponent> Camera;

    int64 AppliedRevision = -1;
    float Elapsed = 0.0f;
    FLinearColor StateColor = FLinearColor(0.08f, 0.68f, 0.72f, 1.0f);
};
