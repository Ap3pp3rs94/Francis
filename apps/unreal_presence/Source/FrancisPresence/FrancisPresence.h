#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FFrancisPresenceBridge;

DECLARE_LOG_CATEGORY_EXTERN(LogFrancisPresence, Log, All);

class FFrancisPresenceModule final : public IModuleInterface
{
public:
    static FFrancisPresenceModule& Get();
    static bool IsAvailable();

    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

    FFrancisPresenceBridge* GetBridge() const;

private:
    TUniquePtr<FFrancisPresenceBridge> Bridge;
};
