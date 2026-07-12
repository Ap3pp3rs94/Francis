#include "FrancisPresence.h"

#include "FrancisPresenceBridge.h"

DEFINE_LOG_CATEGORY(LogFrancisPresence);

IMPLEMENT_PRIMARY_GAME_MODULE(FFrancisPresenceModule, FrancisPresence, "FrancisPresence");

FFrancisPresenceModule& FFrancisPresenceModule::Get()
{
    return FModuleManager::LoadModuleChecked<FFrancisPresenceModule>("FrancisPresence");
}

bool FFrancisPresenceModule::IsAvailable()
{
    return FModuleManager::Get().IsModuleLoaded("FrancisPresence");
}

void FFrancisPresenceModule::StartupModule()
{
    Bridge = MakeUnique<FFrancisPresenceBridge>();
    Bridge->Start();
}

void FFrancisPresenceModule::ShutdownModule()
{
    if (Bridge)
    {
        Bridge->Stop();
        Bridge.Reset();
    }
}

FFrancisPresenceBridge* FFrancisPresenceModule::GetBridge() const
{
    return Bridge.Get();
}
