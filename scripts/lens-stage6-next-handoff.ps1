[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(1, 50)]
  [int]$Limit = 5,

  [string]$CompletionAuditJsonPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Get-PropertyValue {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [AllowNull()]
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }

  if ($Payload -is [System.Collections.IDictionary]) {
    if ($Payload.Contains($Name) -and $null -ne $Payload[$Name]) {
      return $Payload[$Name]
    }
    return $Default
  }

  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function ConvertTo-StringArray {
  param(
    [AllowNull()]
    [object]$Value
  )

  if ($null -eq $Value) {
    return @()
  }

  if ($Value -is [string]) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return @()
    }
    return @($Value)
  }

  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }

  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
}

function New-Check {
  param(
    [string]$Id,
    [string]$Status,
    [bool]$Passed,
    [string]$Evidence,
    [string]$Reason
  )

  return [ordered]@{
    id = $Id
    status = $Status
    passed = $Passed
    evidence = $Evidence
    reason = $Reason
  }
}

function New-Stage6CompletionAuditRuntimeOperatorHandoff {
  return [ordered]@{
    source = 'stage6_completion_audit_launch_on_hotkey_readback_required'
    status = 'operator_opt_in_required'
    next_operator_action_requirement = 'stage6_completion_audit_runtime_readback'
    next_operator_action = [ordered]@{
      id = 'run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback'
      route = '/lens/status'
      method = 'LOCAL_SCRIPT'
      mode = 'runtime_readback'
      proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey'
      live_effect = 'reads back the launch-on-hotkey runtime posture before advancing the Stage 6 authority-readiness handoff'
      operator_supplied_values_required = $false
      requires_explicit_operator_opt_in = $true
      script_would_execute = $false
      script_would_mutate = $false
      script_would_request_authority = $false
      script_would_grant_authority = $false
      script_would_decide_approval = $false
    }
    next_operator_command = [ordered]@{
      command = '.\scripts\lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey'
      mode = 'Status'
      requires_confirmation = $false
      requires_explicit_operator_opt_in = $true
      requires_approval_id = $false
      requires_operator_approval_decision = $false
      completion_audit_json_parameter = '-CompletionAuditJsonPath'
    }
    read_only_status_command = '.\scripts\lens-stage6-next-handoff.ps1 -Mode Status'
    operator_sequence_command_availability = [ordered]@{
      available_now_count = 1
      preview_only_count = 0
      sequence_length = 1
      truthful = $true
    }
    read_only_contract = $true
    diagnostic_only = $true
    approval_request_write_if_run = $false
    approval_decision_authority = $false
    would_execute = $false
    would_mutate = $false
  }
}

function New-Stage6CompletionAuditReadbackOperatorHandoff {
  param(
    [AllowNull()]
    [object]$RecommendedHandoff,

    [string]$RecommendedNextSlice,
    [string]$RecommendedProofScript,
    [string]$RecommendedRoute,
    [string]$RecommendedReadinessRoute,
    [string]$AuthorityRequired,
    [bool]$AuthorityGranted
  )

  $Command = $RecommendedProofScript.Replace('/', '\')
  if ($Command.StartsWith('scripts\')) {
    $Command = ".\$Command"
  }
  $ScriptWouldExecute = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_execute' -Default $false)
  $ScriptWouldMutate = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_mutate' -Default $false)
  $ScriptWouldRequestAuthority = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_request_authority' -Default $false)
  $ScriptWouldGrantAuthority = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_grant_authority' -Default $false)
  $ScriptWouldDecideApproval = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_decide_approval' -Default $false)
  $ScriptWouldWriteMemory = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_write_memory' -Default $false)
  $ScriptWouldClaimResident = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_claim_resident' -Default $false)
  $ScriptWouldStartService = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_start_service' -Default $false)
  $ScriptWouldWriteServiceConfig = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_write_service_config' -Default $false)
  $ScriptWouldWriteReceipt = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'would_write_receipt' -Default $false)
  $RequiresExplicitOptIn = $ScriptWouldExecute -or $ScriptWouldMutate -or $ScriptWouldWriteServiceConfig -or $ScriptWouldWriteReceipt
  $ReadOnlyContract = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'read_only_contract' -Default (-not $RequiresExplicitOptIn))
  $DiagnosticOnly = [bool](Get-PropertyValue -Payload $RecommendedHandoff -Name 'diagnostic_only' -Default $true)

  return [ordered]@{
    source = 'stage6_completion_audit_recommended_handoff'
    status = 'readback_action_available'
    next_operator_action_requirement = 'stage6_completion_audit_recommended_readback'
    next_operator_action = [ordered]@{
      id = $RecommendedNextSlice
      route = $RecommendedRoute
      readiness_route = $RecommendedReadinessRoute
      method = 'LOCAL_SCRIPT'
      mode = 'Status'
      proof_script = $RecommendedProofScript
      live_effect = 'reads back the completion-audit recommended Stage 6 handoff'
      authority_required = $AuthorityRequired
      authority_granted = $AuthorityGranted
      operator_supplied_values_required = $false
      script_would_execute = $ScriptWouldExecute
      script_would_mutate = $ScriptWouldMutate
      script_would_request_authority = $ScriptWouldRequestAuthority
      script_would_grant_authority = $ScriptWouldGrantAuthority
      script_would_decide_approval = $ScriptWouldDecideApproval
      script_would_write_service_config = $ScriptWouldWriteServiceConfig
      script_would_write_receipt = $ScriptWouldWriteReceipt
      script_would_start_service = $ScriptWouldStartService
      script_would_write_memory = $ScriptWouldWriteMemory
      script_would_claim_resident = $ScriptWouldClaimResident
    }
    next_operator_command = [ordered]@{
      command = $Command
      mode = 'Status'
      requires_confirmation = $false
      requires_explicit_operator_opt_in = $RequiresExplicitOptIn
      requires_actor = $false
      requires_approval_id = $false
      requires_operator_approval_decision = $false
    }
    read_only_status_command = '.\scripts\lens-stage6-next-handoff.ps1 -Mode Status'
    operator_sequence_command_availability = [ordered]@{
      available_now_count = 1
      preview_only_count = 0
      sequence_length = 1
      truthful = $true
    }
    read_only_contract = $ReadOnlyContract
    diagnostic_only = $DiagnosticOnly
    approval_request_write_if_run = $false
    authority_grant_receipt_write_if_run = $false
    approval_decision_authority = $false
    would_execute = $ScriptWouldExecute
    would_mutate = $ScriptWouldMutate
  }
}

function Get-ApprovalReadbackLatestApprovedId {
  param(
    [AllowNull()]
    [object]$Readback
  )

  foreach ($Item in @(
      Get-PropertyValue -Payload $Readback -Name 'items' -Default @()
    )) {
    if (
      [string](Get-PropertyValue -Payload $Item -Name 'status' -Default '') -eq 'approved' -and
      -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $Item -Name 'id' -Default ''))
    ) {
      return [string](Get-PropertyValue -Payload $Item -Name 'id' -Default '')
    }
  }

  $Latest = Get-PropertyValue -Payload $Readback -Name 'latest' -Default ([ordered]@{})
  if (
    [string](Get-PropertyValue -Payload $Latest -Name 'status' -Default '') -eq 'approved' -and
    -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $Latest -Name 'id' -Default ''))
  ) {
    return [string](Get-PropertyValue -Payload $Latest -Name 'id' -Default '')
  }

  return [string](Get-PropertyValue -Payload $Readback -Name 'latest_approval_id' -Default '')
}

function Get-ApprovalReadbackLatestPendingId {
  param(
    [AllowNull()]
    [object]$Readback
  )

  foreach ($Item in @(
      Get-PropertyValue -Payload $Readback -Name 'items' -Default @()
    )) {
    if (
      [string](Get-PropertyValue -Payload $Item -Name 'status' -Default '') -eq 'pending' -and
      -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $Item -Name 'id' -Default ''))
    ) {
      return [string](Get-PropertyValue -Payload $Item -Name 'id' -Default '')
    }
  }

  $Latest = Get-PropertyValue -Payload $Readback -Name 'latest' -Default ([ordered]@{})
  if (
    [string](Get-PropertyValue -Payload $Latest -Name 'status' -Default '') -eq 'pending' -and
    -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $Latest -Name 'id' -Default ''))
  ) {
    return [string](Get-PropertyValue -Payload $Latest -Name 'id' -Default '')
  }

  return [string](Get-PropertyValue -Payload $Readback -Name 'latest_pending_approval_id' -Default '')
}

function Get-AuthorityGrantActiveReceiptId {
  param(
    [AllowNull()]
    [object]$Readback
  )

  foreach ($Name in @('active_authority_grant', 'active_latest', 'active_grant')) {
    $Active = Get-PropertyValue -Payload $Readback -Name $Name -Default ([ordered]@{})
    $ReceiptId = [string](Get-PropertyValue -Payload $Active -Name 'receipt_id' -Default '')
    if (-not [string]::IsNullOrWhiteSpace($ReceiptId)) {
      return $ReceiptId
    }
  }

  return [string](Get-PropertyValue -Payload $Readback -Name 'active_grant_receipt_id' -Default '')
}

function New-ResidentRuntimeAuthorityRequestOperatorHandoff {
  param(
    [AllowNull()]
    [object]$SourceHandoff,

    [AllowNull()]
    [object]$ResidentRuntimeAuthorityRequests,

    [AllowNull()]
    [object]$ResidentRuntimeAuthorityGrants,

    [string]$CompletionAuditJsonPath = ''
  )

  $ReceiptReviewReadbackCommand = '.\scripts\lens-stage6-next-handoff.ps1 -Mode Status'
  if (-not [string]::IsNullOrWhiteSpace($CompletionAuditJsonPath)) {
    $EscapedCompletionAuditJsonPath = $CompletionAuditJsonPath.Replace("'", "''")
    $ReceiptReviewReadbackCommand = ".\scripts\lens-stage6-next-handoff.ps1 -Mode Status -CompletionAuditJsonPath '$EscapedCompletionAuditJsonPath'"
  }

  $FirstBlockedRequirementHandoff = Get-PropertyValue `
    -Payload $SourceHandoff `
    -Name 'resident_runtime_authority_grant_first_blocked_requirement_handoff' `
    -Default ([ordered]@{})
  $RequestRoute = [string](Get-PropertyValue `
      -Payload $FirstBlockedRequirementHandoff `
      -Name 'request_route' `
      -Default '/lens/resident-runtime/authority-grant/request')
  $RequestsRoute = [string](Get-PropertyValue `
      -Payload $FirstBlockedRequirementHandoff `
      -Name 'requests_route' `
      -Default '/lens/resident-runtime/authority-grant/requests')
  $ReadinessRoute = [string](Get-PropertyValue `
      -Payload $FirstBlockedRequirementHandoff `
      -Name 'readiness_route' `
      -Default '/lens/resident-runtime/authority-grant/readiness')
  $ApprovalAction = [string](Get-PropertyValue `
      -Payload $FirstBlockedRequirementHandoff `
      -Name 'approval_action' `
      -Default 'lens.resident_runtime.execution_authority')
  $ApprovedApprovalId = Get-ApprovalReadbackLatestApprovedId -Readback $ResidentRuntimeAuthorityRequests
  $PendingApprovalId = Get-ApprovalReadbackLatestPendingId -Readback $ResidentRuntimeAuthorityRequests
  $ActiveGrantReceiptId = Get-AuthorityGrantActiveReceiptId -Readback $ResidentRuntimeAuthorityGrants
  $ApiBaseUrl = 'http://127.0.0.1:8000'
  $GrantRoute = '/lens/resident-runtime/authority-grant'
  $RequestCommand = (
    "`$body = @{ actor = '<actor>'; reason = '<reason>' } | ConvertTo-Json -Compress; " +
    "Invoke-RestMethod -Method Post -Uri '$ApiBaseUrl$RequestRoute' -ContentType 'application/json' -Body `$body"
  )
  $DecisionCommand = (
    "`$body = @{ id = '$PendingApprovalId'; action = 'approve'; comment = '<comment>'; actor = '<actor>' } | ConvertTo-Json -Compress; " +
    "Invoke-RestMethod -Method Post -Uri '$ApiBaseUrl/approvals/decision' -ContentType 'application/json' -Body `$body"
  )
  $GrantCommand = (
    "`$body = @{ approval_id = '$ApprovedApprovalId'; actor = '<actor>'; reason = '<reason>'; lease_seconds = 3600 } | ConvertTo-Json -Compress; " +
    "Invoke-RestMethod -Method Post -Uri '$ApiBaseUrl$GrantRoute' -ContentType 'application/json' -Body `$body"
  )

  if (-not [string]::IsNullOrWhiteSpace($ActiveGrantReceiptId)) {
    return [ordered]@{
      source = 'resident_runtime_authority_readiness_handoff'
      status = 'authority_grant_receipt_already_active'
      next_operator_action_requirement = 'resident_runtime_execution_authority_grant_receipt'
      next_operator_action = [ordered]@{
        id = 'review_resident_runtime_execution_authority_grant_receipt'
        route = '/lens/resident-runtime/authority-grant/grants'
        readiness_route = $ReadinessRoute
        method = 'GET'
        approval_action = $ApprovalAction
        mode = 'readback'
        live_effect = 'resident runtime authority grant receipt is already recorded'
        latest_receipt_id = $ActiveGrantReceiptId
        operator_supplied_values_required = $false
        script_would_execute = $false
        script_would_mutate = $false
        script_would_request_authority = $false
        script_would_grant_authority = $false
        script_would_decide_approval = $false
      }
      next_operator_command = [ordered]@{
        command = $ReceiptReviewReadbackCommand
        mode = 'Status'
        requires_confirmation = $false
        requires_explicit_operator_opt_in = $false
        requires_actor = $false
        requires_approval_id = $false
        requires_operator_approval_decision = $false
      }
      read_only_status_command = $ReceiptReviewReadbackCommand
      operator_sequence_command_availability = [ordered]@{
        available_now_count = 1
        preview_only_count = 0
        sequence_length = 1
        truthful = $true
      }
      read_only_contract = $true
      diagnostic_only = $true
      approval_request_write_if_run = $false
      authority_grant_receipt_write_if_run = $false
      approval_decision_authority = $false
      would_execute = $false
      would_mutate = $false
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($ApprovedApprovalId)) {
    return [ordered]@{
      source = 'resident_runtime_authority_readiness_handoff'
      status = 'approved_authority_request_selected'
      next_operator_action_requirement = 'exact_resident_runtime_execution_authority_approval'
      next_operator_action = [ordered]@{
        id = 'select_exact_approved_resident_runtime_execution_authority_request'
        route = $RequestsRoute
        requests_route = $RequestsRoute
        readiness_route = $ReadinessRoute
        method = 'GET'
        approval_action = $ApprovalAction
        approved_approval_id = $ApprovedApprovalId
        requires = [string[]]@('exact approved resident runtime authority approval_id')
        mode = 'approval_readback'
        live_effect = 'selects the approved resident-runtime authority request; no authority grant receipt is written'
        operator_supplied_values_required = $false
        script_would_execute = $false
        script_would_mutate = $false
        script_would_request_authority = $false
        script_would_grant_authority = $false
        script_would_decide_approval = $false
        follow_up_authority_grant_command = [ordered]@{
          command = $GrantCommand
          route = $GrantRoute
          method = 'POST'
          api_base_url = $ApiBaseUrl
          payload_shape = [ordered]@{
            approval_id = $ApprovedApprovalId
            actor = '<actor>'
            reason = '<reason>'
            lease_seconds = 3600
          }
          required_scope = 'system.write'
          requires_running_api = $true
          requires_operator_actor = $true
          requires_approval_id = $true
          would_grant_authority_if_run = $true
          status_readback_would_grant_authority = $false
          preview_only = $true
          availability_reason = 'approved_request_selected_but_authority_grant_is_separate_operator_step'
        }
      }
      next_operator_command = [ordered]@{
        command = $ReceiptReviewReadbackCommand
        mode = 'Status'
        route = $RequestsRoute
        method = 'GET'
        requires_confirmation = $false
        requires_explicit_operator_opt_in = $false
        requires_actor = $false
        requires_approval_id = $false
        requires_operator_approval_decision = $false
      }
      read_only_status_command = $ReceiptReviewReadbackCommand
      next_operator_actor_scope_readiness = [ordered]@{
        ready = $true
        reason = 'not_required'
        actor_present = $false
        scope_required = $false
        required_scope = ''
        action_id = 'select_exact_approved_resident_runtime_execution_authority_request'
        route = $RequestsRoute
        method = 'GET'
        operator_must_supply_actor = $false
        env_var = 'FRANCIS_API_ACTOR_SCOPES'
        json_shape = [ordered]@{ '<actor>' = [string[]]@('system.write') }
        powershell_example = '$env:FRANCIS_API_ACTOR_SCOPES = ''{"<actor>":["system.write"]}'''
      }
      operator_sequence_command_availability = [ordered]@{
        available_now_count = 1
        preview_only_count = 0
        sequence_length = 1
        truthful = $true
      }
      read_only_contract = $true
      diagnostic_only = $true
      approval_request_write_if_run = $false
      authority_grant_receipt_write_if_run = $false
      approval_decision_authority = $false
      would_execute = $false
      would_mutate = $false
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($PendingApprovalId)) {
    return [ordered]@{
      source = 'resident_runtime_authority_readiness_handoff'
      status = 'operator_approval_decision_required'
      next_operator_action_requirement = 'exact_resident_runtime_execution_authority_approval'
      next_operator_action = [ordered]@{
        id = 'await_resident_runtime_execution_authority_approval'
        route = $RequestsRoute
        readiness_route = $ReadinessRoute
        method = 'GET'
        approval_action = $ApprovalAction
        pending_approval_id = $PendingApprovalId
        mode = 'approval_wait'
        live_effect = 'approval request exists; operator approval decision is required before grant receipt'
        operator_supplied_values_required = $false
        requires_operator_approval_decision = $true
        script_would_execute = $false
        script_would_mutate = $false
        script_would_request_authority = $false
        script_would_grant_authority = $false
        script_would_decide_approval = $false
        approval_decision_command = [ordered]@{
          command = $DecisionCommand
          route = '/approvals/decision'
          method = 'POST'
          api_base_url = $ApiBaseUrl
          payload_shape = [ordered]@{
            id = $PendingApprovalId
            action = 'approve'
            comment = '<comment>'
            actor = '<actor>'
          }
          required_scope = 'approvals.decide'
          requires_running_api = $true
          requires_operator_actor = $true
          requires_local_caller_unless_remote_enabled = $true
          remote_enable_env_var = 'FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS'
          would_decide_approval_if_run = $true
          status_readback_would_decide_approval = $false
        }
      }
      next_operator_command = [ordered]@{
        command = $ReceiptReviewReadbackCommand
        mode = 'Status'
        route = $RequestsRoute
        method = 'GET'
        requires_confirmation = $false
        requires_explicit_operator_opt_in = $false
        requires_actor = $false
        requires_approval_id = $false
        requires_operator_approval_decision = $true
        approval_decision_command = [ordered]@{
          command = $DecisionCommand
          route = '/approvals/decision'
          method = 'POST'
          api_base_url = $ApiBaseUrl
          payload_shape = [ordered]@{
            id = $PendingApprovalId
            action = 'approve'
            comment = '<comment>'
            actor = '<actor>'
          }
          required_scope = 'approvals.decide'
          requires_running_api = $true
          requires_operator_actor = $true
          requires_local_caller_unless_remote_enabled = $true
          remote_enable_env_var = 'FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS'
          would_decide_approval_if_run = $true
          status_readback_would_decide_approval = $false
        }
      }
      read_only_status_command = $ReceiptReviewReadbackCommand
      operator_sequence_command_availability = [ordered]@{
        available_now_count = 1
        preview_only_count = 0
        sequence_length = 1
        truthful = $true
      }
      read_only_contract = $true
      diagnostic_only = $true
      approval_request_write_if_run = $false
      authority_grant_receipt_write_if_run = $false
      approval_decision_authority = $false
      would_execute = $false
      would_mutate = $false
    }
  }

  return [ordered]@{
    source = 'resident_runtime_authority_readiness_handoff'
    status = 'operator_action_available'
    next_operator_action_requirement = 'exact_resident_runtime_execution_authority_approval'
    next_operator_action = [ordered]@{
      id = 'request_resident_runtime_execution_authority'
      route = $RequestRoute
      requests_route = $RequestsRoute
      readiness_route = $ReadinessRoute
      method = 'POST'
      approval_action = $ApprovalAction
      requires = [string[]]@('system.write actor scope', 'explicit -ConfirmRequest operator execution')
      mode = 'approval_request'
      live_effect = 'creates a pending resident-runtime execution authority approval request only'
      operator_supplied_values_required = $true
      script_would_execute = $false
      script_would_mutate = $false
      script_would_request_authority = $true
      script_would_grant_authority = $false
      script_would_decide_approval = $false
      approval_request_command = [ordered]@{
        command = $RequestCommand
        route = $RequestRoute
        method = 'POST'
        api_base_url = $ApiBaseUrl
        payload_shape = [ordered]@{
          actor = '<actor>'
          reason = '<reason>'
        }
        required_scope = 'system.write'
        requires_running_api = $true
        requires_operator_actor = $true
        would_request_approval_if_run = $true
        status_readback_would_request_approval = $false
      }
    }
    next_operator_command = [ordered]@{
      command = $RequestCommand
      mode = 'ApiRequest'
      route = $RequestRoute
      method = 'POST'
      requires_confirmation = $true
      requires_explicit_operator_opt_in = $true
      requires_actor = $true
      requires_approval_id = $false
      requires_operator_approval_decision = $false
    }
    read_only_status_command = $ReceiptReviewReadbackCommand
    next_operator_actor_scope_readiness = [ordered]@{
      ready = $false
      reason = 'actor_not_supplied'
      actor_present = $false
      scope_required = $true
      required_scope = 'system.write'
      action_id = 'request_resident_runtime_execution_authority'
      route = $RequestRoute
      method = 'POST'
      operator_must_supply_actor = $true
      env_var = 'FRANCIS_API_ACTOR_SCOPES'
      json_shape = [ordered]@{ '<actor>' = [string[]]@('system.write') }
      powershell_example = '$env:FRANCIS_API_ACTOR_SCOPES = ''{"<actor>":["system.write"]}'''
    }
    operator_sequence_command_availability = [ordered]@{
      available_now_count = 1
      preview_only_count = 0
      sequence_length = 1
      truthful = $true
    }
    read_only_contract = $true
    diagnostic_only = $true
    approval_request_write_if_run = $true
    approval_decision_authority = $false
    would_execute = $false
    would_mutate = $false
  }
}

function Find-Criterion {
  param(
    [AllowNull()]
    [object]$Criteria,
    [string]$CriterionId
  )

  foreach ($Criterion in @($Criteria)) {
    if ([string](Get-PropertyValue -Payload $Criterion -Name 'id' -Default '') -eq $CriterionId) {
      return $Criterion
    }
  }
  return $null
}

function Invoke-LensStatusReadback {
  param([int]$StatusLimit)

  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $Python) {
    throw 'Python is required to read lens_status.'
  }

  $PreviousPythonPath = $env:PYTHONPATH
  $SrcPath = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SrcPath
  } elseif ($PreviousPythonPath -notlike "*$SrcPath*") {
    $env:PYTHONPATH = "$SrcPath;$PreviousPythonPath"
  }

$PythonCode = @"
import json
from francis.lens.status import lens_status
print(json.dumps(lens_status(limit=$StatusLimit)))
"@

  try {
    $Output = & $Python.Source -c $PythonCode 2>&1
    $ExitCode = $LASTEXITCODE
  } finally {
    $env:PYTHONPATH = $PreviousPythonPath
  }

  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  if ($ExitCode -ne 0) {
    throw "lens_status readback failed with exit code $ExitCode. $Text"
  }

  return $Text | ConvertFrom-Json -ErrorAction Stop
}

function Invoke-JsonScriptReadback {
  param(
    [string]$ScriptPath,
    [hashtable]$Parameters = @{}
  )

  $Output = & $ScriptPath @Parameters 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"

  if ([string]::IsNullOrWhiteSpace($Text)) {
    throw "JSON script readback produced no output: $ScriptPath"
  }

  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    throw "JSON script readback failed to parse: $ScriptPath. $Text"
  }

  return [ordered]@{
    exit_code = [int]$ExitCode
    payload = $Payload
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$StatusReadback = Invoke-LensStatusReadback -StatusLimit $Limit
$Stage6PrerequisiteBringupPlanScript = Join-Path $PSScriptRoot 'lens-stage6-prerequisite-bringup-plan.ps1'
$PersistentSupervisionResidentClaimBoundaryScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-resident-claim-boundary-proof.ps1'
$Stage6PrerequisiteBringupDataDir = [string]$env:FRANCIS_DATA_DIR
if ([string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupDataDir)) {
  $Stage6PrerequisiteBringupDataDir = Join-Path $RepoRoot 'data'
}
$Stage6PrerequisiteBringupPlanResult = Invoke-JsonScriptReadback `
  -ScriptPath $Stage6PrerequisiteBringupPlanScript `
  -Parameters @{ Mode = 'Status'; DataDir = $Stage6PrerequisiteBringupDataDir }
$Stage6PrerequisiteBringupPlan = $Stage6PrerequisiteBringupPlanResult.payload
$Stage6PrerequisiteBringupPlanGovernance = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'governance' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable'
)
$Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'missing_required_before_enable'
)
$Stage6PrerequisiteBringupPlanNextOperatorAction = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanNextOperatorCommand = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_command' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_actor_scope_readiness' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanCommandAvailability = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'operator_sequence_command_availability' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanAllowedFirstMissingTruthfulGaps = @(
  'resident_host_process_not_supervised',
  'resident_supervision_not_persistent',
  'summon_tray_presence_blocker_boundary',
  'os_level_command_palette_binding',
  'summon_overlay_window_blocker_boundary',
  'summon_anywhere_blockers'
)
$Stage6PrerequisiteBringupPlanFirstMissingRequirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_requirement' -Default '')
$Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
$Stage6PrerequisiteBringupPlanNextOperatorRequirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
$Stage6PrerequisiteBringupPlanStatus = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'status' -Default '')
$Stage6PrerequisiteBringupPlanCurrentGap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default '')
$Stage6PrerequisiteBringupPlanCurrentGapBasis = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap_basis' -Default '')
$Stage6PrerequisiteBringupNextOperatorActionId = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'id' -Default ''
)
$Stage6PrerequisiteBringupNextOperatorActionMethod = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'method' -Default ''
)
$Stage6PrerequisiteBringupNextOperatorCommandMode = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorCommand -Name 'mode' -Default ''
)
$Stage6PrerequisiteBringupPlanCommonObserved = (
  [int]$Stage6PrerequisiteBringupPlanResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'kind' -Default '') -eq 'lens.stage6.prerequisite_bringup.plan' -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'stage_state' -Default '') -eq 'active' -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'ready_to_close' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'acceptance_criterion' -Default '') -eq 'system_resident_presence' -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanCurrentGap) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanCurrentGapBasis) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupNextOperatorActionId) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_mutate' -Default $true) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupNextOperatorCommandMode) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanCommandAvailability -Name 'truthful' -Default $false) -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'resident_host_process' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'tray_presence' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'overlay_window' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'summon_binding' -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'plan_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'requires_explicit_operator_execution' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'actor_scope_readback' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'would_mutate' -Default $true)
)
$Stage6PrerequisiteBringupPlanBlockedObserved = (
  $Stage6PrerequisiteBringupPlanCommonObserved -and
  $Stage6PrerequisiteBringupPlanStatus -eq 'blocked' -and
  $Stage6PrerequisiteBringupPlanCurrentGap -eq 'persistent_supervision_required_prerequisites_missing' -and
  $Stage6PrerequisiteBringupPlanCurrentGapBasis -eq 'missing_required_before_enable' -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanFirstMissingRequirement) -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains $Stage6PrerequisiteBringupPlanFirstMissingRequirement -and
  $Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable -contains $Stage6PrerequisiteBringupPlanFirstMissingRequirement -and
  $Stage6PrerequisiteBringupPlanAllowedFirstMissingTruthfulGaps -contains $Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $true) -and
  $Stage6PrerequisiteBringupPlanNextOperatorRequirement -eq $Stage6PrerequisiteBringupPlanFirstMissingRequirement
)
$Stage6PrerequisiteBringupPlanReadyForEnablementObserved = (
  $Stage6PrerequisiteBringupPlanCommonObserved -and
  $Stage6PrerequisiteBringupPlanStatus -eq 'ready_for_persistent_supervision_enablement_sequence' -and
  @($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable).Count -eq 0 -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false) -and
  $Stage6PrerequisiteBringupPlanCurrentGapBasis -eq 'persistent_supervision_plan.next_smallest_truthful_gap' -and
  $Stage6PrerequisiteBringupPlanNextOperatorRequirement -eq 'persistent_supervision_enablement'
)
$Stage6PrerequisiteBringupPlanAppliedObserved = (
  $Stage6PrerequisiteBringupPlanCommonObserved -and
  $Stage6PrerequisiteBringupPlanStatus -eq 'persistent_supervision_enablement_applied' -and
  @($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable).Count -eq 0 -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false) -and
  $Stage6PrerequisiteBringupPlanCurrentGap -ne 'persistent_supervision_required_prerequisites_missing' -and
  @(
    'persistent_supervision_plan.next_smallest_truthful_gap',
    'persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap'
  ) -contains $Stage6PrerequisiteBringupPlanCurrentGapBasis -and
  $Stage6PrerequisiteBringupPlanNextOperatorRequirement -eq 'persistent_supervision_enablement_receipt' -and
  $Stage6PrerequisiteBringupNextOperatorActionId -eq 'review_persistent_supervision_enablement_receipt' -and
  $Stage6PrerequisiteBringupNextOperatorActionMethod -eq 'GET' -and
  $Stage6PrerequisiteBringupNextOperatorCommandMode -eq 'Status'
)
$Stage6PrerequisiteBringupPlanObserved = (
  $Stage6PrerequisiteBringupPlanBlockedObserved -or
  $Stage6PrerequisiteBringupPlanReadyForEnablementObserved -or
  $Stage6PrerequisiteBringupPlanAppliedObserved
)

$Stage6Readiness = Get-PropertyValue -Payload $StatusReadback -Name 'stage6_readiness'
$ClosureReadback = Get-PropertyValue -Payload $Stage6Readiness -Name 'closure_readback'
$Criteria = Get-PropertyValue -Payload $ClosureReadback -Name 'criteria' -Default @()
$BlockedCriteria = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ClosureReadback -Name 'blocked_criteria')
$ReadyCriteria = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ClosureReadback -Name 'ready_criteria')
$StageNextGap = [string](Get-PropertyValue -Payload $ClosureReadback -Name 'next_smallest_truthful_gap' -Default '')

$FirstBlockedCriterionId = ''
if (@($BlockedCriteria).Count -gt 0) {
  $FirstBlockedCriterionId = [string]$BlockedCriteria[0]
}
$FirstBlockedCriterion = Find-Criterion -Criteria $Criteria -CriterionId $FirstBlockedCriterionId
$CriterionHandoff = Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'handoff' -Default ([ordered]@{})
$FirstBlockerFamily = [string](Get-PropertyValue -Payload $CriterionHandoff -Name 'first_blocker_family' -Default '')
$FirstBlockerFamilyHandoff = Get-PropertyValue -Payload $CriterionHandoff -Name 'first_blocker_family_handoff' -Default ([ordered]@{})
$FirstFamilyCompletionAuditHandoff = Get-PropertyValue -Payload $CriterionHandoff -Name 'first_blocker_family_completion_audit_handoff' -Default ([ordered]@{})
$FamilyChainCompletionAuditHandoff = Get-PropertyValue -Payload $CriterionHandoff -Name 'summon_anywhere_family_chain_completion_audit_handoff' -Default ([ordered]@{})
$ResidentHostReadback = Get-PropertyValue -Payload $StatusReadback -Name 'resident_host' -Default ([ordered]@{})
$ResidentRuntimeAuthorityRequests = Get-PropertyValue -Payload $ResidentHostReadback -Name 'resident_runtime_authority_requests' -Default $null
if ($null -eq $ResidentRuntimeAuthorityRequests) {
  $ResidentRuntimeAuthorityRequests = Get-PropertyValue -Payload $StatusReadback -Name 'resident_runtime_authority_requests' -Default ([ordered]@{})
}
$ResidentRuntimeAuthorityGrants = Get-PropertyValue -Payload $ResidentHostReadback -Name 'resident_runtime_authority_grant_receipts' -Default $null
if ($null -eq $ResidentRuntimeAuthorityGrants) {
  $ResidentRuntimeAuthorityGrants = Get-PropertyValue -Payload $StatusReadback -Name 'resident_runtime_authority_grant_receipts' -Default ([ordered]@{})
}
$FreshResidentRuntimeCandidateSupervised = [bool](
  Get-PropertyValue -Payload $ResidentHostReadback -Name 'fresh_resident_runtime_candidate_supervised' -Default $false
)
$ResidentRuntimeCandidateSupervised = [bool](
  Get-PropertyValue -Payload $ResidentHostReadback -Name 'resident_runtime_candidate_supervised' -Default $false
)
$SupervisorFreshnessStatus = [string](
  Get-PropertyValue -Payload $ResidentHostReadback -Name 'supervisor_freshness_status' -Default ''
)
$PersistentSupervisionPlanReadback = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_plan' -Default ([ordered]@{})
$PersistentSupervisionEnablementReadback = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement' -Default ([ordered]@{})
$PersistentSupervisionEnablementAuthorityReadiness = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement_authority_readiness' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReadiness = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement_execution_readiness' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceipts = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement_execution_receipts' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceiptLatest = Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'latest' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceiptGovernance = Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'governance' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceiptPostPlan = Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptLatest -Name 'post_plan' -Default ([ordered]@{})
$PersistentSupervisionMissingRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'missing_required_before_enable'
)
$PersistentSupervisionEnablementMissingRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionEnablementReadback -Name 'missing_required_before_enable'
)
$PersistentSupervisionFirstMissingRequiredBeforeEnable = [string](
  Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'first_missing_required_before_enable' -Default ''
)
$PersistentSupervisionFirstMissingRequirementHandoff = Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'first_missing_requirement_handoff' -Default ([ordered]@{})
$ActivationStateReadback = Get-PropertyValue -Payload $ResidentHostReadback -Name 'activation_state' -Default ([ordered]@{})
$ActivationExecutionHandoff = Get-PropertyValue -Payload $ActivationStateReadback -Name 'latest_execution_handoff' -Default ([ordered]@{})
$ActivationExecutionHandoffReady = (
  [bool](Get-PropertyValue -Payload $ActivationStateReadback -Name 'latest_execution_handoff_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_mutate' -Default $false)
)
$PersistentSupervisionFirstMissingRequirementHandoffReady = (
  -not [string]::IsNullOrWhiteSpace($PersistentSupervisionFirstMissingRequiredBeforeEnable) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'id' -Default '') -eq $PersistentSupervisionFirstMissingRequiredBeforeEnable -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_mutate' -Default $false)
)
$FirstMissingHandoffIsLiveUnsupervisedProcess = (
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'blocker' -Default '') -eq 'resident_host_process_not_supervised' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'requirement_state' -Default '') -eq 'foreground_observed_not_supervised'
)
$EnablementAuthorityBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'blockers' -Default @()
)
$EnablementExecutionBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'blockers' -Default @()
)
$PersistentSupervisionEnablementAuthorityHandoffObserved = (
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement_authority.readiness_audit' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'grant_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'grant_receipt_readback_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'enablement_authority_granted' -Default $true) -and
  $EnablementAuthorityBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement_execution.readiness_audit' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'boundary_observed' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'persistent_supervision_execution_authority' -Default $true) -and
  $EnablementExecutionBlockers -contains 'persistent_supervision_execution_authority_not_granted' -and
  -not $Stage6PrerequisiteBringupPlanAppliedObserved -and
  -not $FirstMissingHandoffIsLiveUnsupervisedProcess
)
$PersistentSupervisionEnablementAuthorityHandoff = [ordered]@{}
if ($PersistentSupervisionEnablementAuthorityHandoffObserved) {
  $PersistentSupervisionEnablementAuthorityHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = 'persistent_supervision_authority_not_granted'
    consumed_audit_next_smallest_truthful_gap = 'persistent_supervision_enablement_denial_boundary'
    next_smallest_truthful_gap = 'persistent_supervision_enablement_authority_not_granted'
    next_step = 'prove_persistent_supervision_enablement_authority_after_candidate_handoff'
    proof_script = 'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status'
    route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'enablement_route' -Default '/lens/host/persistent-supervision/enablement')
    request_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'request_route' -Default '')
    grant_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'authority_route' -Default '')
    grants_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'grants_route' -Default '')
    readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'route' -Default '')
    execution_readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'route' -Default '')
    authority_required = 'persistent_supervision_enablement_authority'
    authority_granted = $false
    enablement_denial_observed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'boundary_observed' -Default $false)
    execution_denial_observed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'boundary_observed' -Default $false)
    persistent_supervision_enablement_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'enablement_authority_granted' -Default $false)
    service_config_write_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'service_config_write_authority' -Default $false)
    persistent_supervision_execution_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'persistent_supervision_execution_authority' -Default $false)
    receipt_write_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'receipt_write_authority' -Default $false)
    resident_claim_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'resident_claim_authority' -Default $false)
    resident_claim_allowed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'resident_claim_allowed' -Default $false)
    service_config_updated = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'service_config_updated' -Default $false)
    applied = $false
    executed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'executed' -Default $false)
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@($EnablementAuthorityBlockers + $EnablementExecutionBlockers | Sort-Object -Unique)
  }
}
$PersistentSupervisionEnablementExecutionReceiptStatus = [string](
  Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptLatest -Name 'status' -Default ''
)
$PersistentSupervisionEnablementReceiptReviewObserved = (
  $Stage6PrerequisiteBringupPlanAppliedObserved -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement_execution.receipts' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'status' -Default '') -eq 'readback_ready' -and
  [int](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'total' -Default 0) -gt 0 -and
  @('service_config_updated', 'service_config_already_enabled') -contains $PersistentSupervisionEnablementExecutionReceiptStatus -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'persistent_supervision_enablement_allowed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'persistent_supervision_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'resident_claim_allowed' -Default $true) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptPostPlan -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_execution_boundary' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'read_only_contract' -Default $false) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'next_step' -Default '') -eq 'review_persistent_supervision_execution_receipts_before_resident_claim_boundary' -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'mutation_authority_granted' -Default $true)
)
$PersistentSupervisionEnablementReceiptReviewHandoff = [ordered]@{}
if ($PersistentSupervisionEnablementReceiptReviewObserved) {
  $PersistentSupervisionEnablementReceiptReviewHandoff = [ordered]@{
    status = 'receipt_reviewed'
    previous_next_smallest_truthful_gap = 'persistent_supervision_execution_boundary'
    next_smallest_truthful_gap = 'persistent_supervision_resident_claim_authority_boundary'
    next_step = 'review_persistent_supervision_resident_claim_boundary_without_runtime_start'
    proof_script = 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status'
    route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'route' -Default '/lens/host/persistent-supervision/enablement/executions')
    readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'readiness_route' -Default '/lens/host/persistent-supervision/enablement/execution/readiness')
    execution_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'execution_route' -Default '/lens/host/persistent-supervision/enablement/execution')
    latest_receipt_id = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptLatest -Name 'receipt_id' -Default '')
    latest_receipt_status = $PersistentSupervisionEnablementExecutionReceiptStatus
    post_plan_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptPostPlan -Name 'next_smallest_truthful_gap' -Default '')
    authority_required = 'resident_claim_authority'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}
$PersistentSupervisionResidentClaimBoundaryResult = [ordered]@{
  exit_code = 0
  payload = [ordered]@{}
}
$PersistentSupervisionResidentClaimBoundary = [ordered]@{}
$PersistentSupervisionResidentClaimBoundaryHandoff = [ordered]@{}
if ($PersistentSupervisionEnablementReceiptReviewObserved) {
  if (-not (Test-Path -LiteralPath $PersistentSupervisionResidentClaimBoundaryScript -PathType Leaf)) {
    throw "Required Lens proof script is missing: $PersistentSupervisionResidentClaimBoundaryScript"
  }
  $PersistentSupervisionResidentClaimBoundaryResult = Invoke-JsonScriptReadback `
    -ScriptPath $PersistentSupervisionResidentClaimBoundaryScript `
    -Parameters @{ Mode = 'Status' }
  $PersistentSupervisionResidentClaimBoundary = Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryResult -Name 'payload' -Default ([ordered]@{})
  $PersistentSupervisionResidentClaimBoundaryHandoff = Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'handoff' -Default ([ordered]@{})
}
$PersistentSupervisionResidentClaimBoundaryHandoffObserved = (
  $PersistentSupervisionEnablementReceiptReviewObserved -and
  [int](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_resident_claim_boundary.proof' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'final_persistent_supervision_authority_family_consumed' -Default $false) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_handoff_source' -Default '') -eq 'persistent_supervision_resident_claim_boundary_handoff' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_next_slice' -Default '') -eq 'run_stage6_lens_completion_audit_after_resident_claim_boundary_readback' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-stage6-completion-audit.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'status' -Default '') -eq 'audit_needed' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_claim_resident' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_write_receipt' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_write_memory' -Default $true)
)
$Stage6CompletionAuditResult = [ordered]@{
  exit_code = 0
  payload = [ordered]@{}
}
$Stage6CompletionAudit = [ordered]@{}
$Stage6CompletionAuditRecommendedHandoff = [ordered]@{}
$ResolvedCompletionAuditJsonPath = ''
if (-not [string]::IsNullOrWhiteSpace($CompletionAuditJsonPath)) {
  if (-not (Test-Path -LiteralPath $CompletionAuditJsonPath -PathType Leaf)) {
    throw "Completion audit JSON readback is missing: $CompletionAuditJsonPath"
  }
  $ResolvedCompletionAuditJsonPath = (Resolve-Path -LiteralPath $CompletionAuditJsonPath).Path
  $Stage6CompletionAuditReadback = Get-Content -LiteralPath $ResolvedCompletionAuditJsonPath -Raw | ConvertFrom-Json -ErrorAction Stop
  $Stage6CompletionAudit = $Stage6CompletionAuditReadback
  $WrappedCompletionAuditPayload = Get-PropertyValue -Payload $Stage6CompletionAuditReadback -Name 'payload' -Default ([ordered]@{})
  if (
    [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'kind' -Default '') -ne 'lens.stage6.completion_audit' -and
    [string](Get-PropertyValue -Payload $WrappedCompletionAuditPayload -Name 'kind' -Default '') -eq 'lens.stage6.completion_audit'
  ) {
    $Stage6CompletionAudit = $WrappedCompletionAuditPayload
  }
  $Stage6CompletionAuditRecommendedHandoff = Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff' -Default ([ordered]@{})
}
$Stage6CompletionAuditReadbackObserved = (
  -not [string]::IsNullOrWhiteSpace($CompletionAuditJsonPath) -and
  [int](Get-PropertyValue -Payload $Stage6CompletionAuditResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'kind' -Default '') -eq 'lens.stage6.completion_audit' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'audit_status' -Default '') -eq 'complete'
)
$Stage6CompletionAuditLaunchOnHotkeyProof = Get-PropertyValue `
  -Payload $Stage6CompletionAudit `
  -Name 'summon_api_launch_on_hotkey_proof' `
  -Default ([ordered]@{})
$Stage6CompletionAuditLaunchOnHotkeyRuntimeReadbackObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'allow_launch_on_hotkey' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditLaunchOnHotkeyProof -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditLaunchOnHotkeyProof -Name 'allow_launch_on_hotkey' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditLaunchOnHotkeyProof -Name 'opened' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditLaunchOnHotkeyProof -Name 'summon_anywhere' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditLaunchOnHotkeyProof -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit'
)
$Stage6CompletionAuditHelpfulNotNoisyRuntimeAuthorityHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'stage6_helpful_not_noisy_runtime_authority_readiness_handoff' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_surface_runtime_not_supervised' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-stage6-checkpoint.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'operator_approval' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'authority_readiness_handoff_ready' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'consumed_resident_surface_foreground_runtime_proof' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'resident_runtime_authority_grant_readiness_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true)
)
$Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff = Get-PropertyValue `
  -Payload $Stage6CompletionAuditRecommendedHandoff `
  -Name 'resident_surface_runtime_supervision_handoff' `
  -Default $Stage6CompletionAuditRecommendedHandoff
$Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'stage6_helpful_not_noisy_resident_surface_runtime_handoff' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq 'resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'id' -Default '') -eq 'resident_surface_runtime_supervision' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_surface_runtime_not_supervised' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'next_step' -Default '') -eq 'resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-resident-surface-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'readiness_route' -Default '') -eq '/lens/resident-runtime/authority-grant/readiness' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'authority_required' -Default '') -eq 'process_supervision_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoff -Name 'would_claim_resident' -Default $true)
)
$Stage6CompletionAuditHelpfulNotNoisyResidentSurfaceRuntimeHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'stage6_helpful_not_noisy_resident_surface_runtime_handoff' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_surface_runtime_not_supervised' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-resident-surface-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'process_supervision_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  (
    $Stage6CompletionAuditResidentSurfaceRuntimeSupervisionHandoffObserved -or
    (
      [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq 'consume_resident_surface_foreground_runtime_proof_before_helpful_not_noisy_claim' -and
      [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'authority_readiness_handoff_ready' -and
      [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'consumed_resident_surface_foreground_runtime_proof' -Default $false) -and
      [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
      [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
      -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
      -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
      -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true) -and
      -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_supervise_process' -Default $true) -and
      -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_claim_resident' -Default $true) -and
      -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $true) -and
      -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_decide_approval' -Default $true)
    )
  )
)
$Stage6CompletionAuditSummonApiLaunchOnHotkeyReadbackHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'stage6_summon_api_launch_on_hotkey_readback_required' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_api_launch_on_hotkey_readback' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq 'run_summon_api_launch_on_hotkey_proof_for_runtime_readback' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-summon-api-execution-proof.ps1 -Mode Status -AllowLaunchOnHotkey' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'launch_on_hotkey_runtime_readback_opt_in' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'proof_readback_required' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_api_launch_on_hotkey_readback' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default '') -eq 'run_summon_api_launch_on_hotkey_proof_for_runtime_readback' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-api-execution-proof.ps1 -Mode Status -AllowLaunchOnHotkey' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/summon/execute' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/summon/readiness' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '') -eq 'launch_on_hotkey_runtime_readback_opt_in' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_claim_resident' -Default $true)
)
$Stage6CompletionAuditResidentRuntimeTrayPresenceHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'api_resident_runtime_execution_tray_presence_handoff' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_tray_presence_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq 'prove_governed_tray_presence_api_execution_after_resident_supervision' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'tray_registration_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'consumed_resident_runtime_api_execution_proof' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_tray_presence_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default '') -eq 'prove_governed_tray_presence_api_execution_after_resident_supervision' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-tray-presence-api-execution-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/tray' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/tray/readiness' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '') -eq 'tray_registration_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_register_tray' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_claim_resident' -Default $true)
)
$Stage6CompletionAuditPersistentSupervisionApiExecutionHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'stage6_persistent_supervision_api_execution_readback_required' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_api_execution_readback' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq 'run_persistent_supervision_api_execution_proof_after_bounded_summon' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-persistent-supervision-api-execution-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'persistent_supervision_execution_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'proof_readback_required' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'consumed_bounded_summon_api_execution_proof' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_api_execution_readback' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default '') -eq 'run_persistent_supervision_api_execution_proof_after_bounded_summon' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-persistent-supervision-api-execution-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/host/persistent-supervision/enablement/execution/apply' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/persistent-supervision/enablement/execution/readiness' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '') -eq 'persistent_supervision_execution_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_service_config' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_receipt' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_claim_resident' -Default $true)
)
$Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryHandoffSource = [string](
  Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default ''
)
$Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryNextSlice = [string](
  Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default ''
)
$Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  @(
    'persistent_supervision_execution_authority_handoff'
    'stage6_persistent_supervision_api_execution_resident_claim_boundary'
  ) -contains $Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryHandoffSource -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_resident_claim_authority_boundary' -and
  @(
    'review_persistent_supervision_resident_claim_boundary_without_runtime_start'
    'resolve_resident_claim_authority_before_persistent_supervision_resident_claim'
  ) -contains $Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryNextSlice -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'resident_claim_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_resident_claim_authority_boundary' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default '') -eq $Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryNextSlice -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/host/persistent-supervision/enablement/execution' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/persistent-supervision/enablement/execution/readiness' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '') -eq 'resident_claim_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'resident_claim_allowed' -Default $true) -and
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'blockers')) -contains 'resident_claim_authority_not_granted'
)
$Stage6CompletionAuditReviewedSummonFirstBlockerHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'stage6_reviewed_summon_anywhere_first_blocker' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq 'run_resident_host_blocker_proof' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'resident_runtime_execution_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'previous_next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default '') -eq 'run_resident_host_blocker_proof' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/host' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/runtime-loop/readiness' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '') -eq 'resident_runtime_execution_authority' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_restart_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_control_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_summon' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_decide_approval' -Default $true)
)
$Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffNextSlice = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default ''
)
$Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffProofScript = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default ''
)
$Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementResidentHostObserved = (
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'family' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_process_not_supervised' -and
  $Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffNextSlice -eq 'resolve_resident_host_process_before_persistent_supervision_enablement' -and
  $Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffProofScript -eq 'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/host' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/runtime-loop/readiness'
)
$Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementTrayPresenceObserved = (
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'id' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'family' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_tray_presence_blocker_boundary' -and
  $Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffNextSlice -eq 'resolve_tray_presence_before_persistent_supervision_enablement' -and
  $Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffProofScript -eq 'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/tray' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/tray/readiness'
)
$Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '') -eq 'persistent_supervision_prerequisites_first_missing_requirement_handoff' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_required_prerequisites_missing' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq $Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffNextSlice -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq $Stage6CompletionAuditPersistentSupervisionFirstMissingHandoffProofScript -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  (
    $Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementResidentHostObserved -or
    $Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementTrayPresenceObserved
  ) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '') -eq 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_decide_approval' -Default $false)
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction = Get-PropertyValue `
  -Payload $Stage6CompletionAuditRecommendedHandoff `
  -Name 'next_operator_action' `
  -Default ([ordered]@{})
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand = Get-PropertyValue `
  -Payload $Stage6CompletionAuditRecommendedHandoff `
  -Name 'next_operator_command' `
  -Default ([ordered]@{})
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction -Name 'id' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'mode' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_operator_action_requirement' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanFirstMissingRequirement = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'first_missing_required_before_enable' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanEffectiveFirstMissingRequirement = if (
  -not [string]::IsNullOrWhiteSpace($Stage6CompletionAuditPrerequisiteBringupOperatorPlanFirstMissingRequirement)
) {
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanFirstMissingRequirement
} else {
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement
}
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanAllowedRequirements = @(
  'resident_host_process',
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRecommendedNextSlice = [string](
  Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffNextStep = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices = [string[]]@()
if (-not [string]::IsNullOrWhiteSpace($Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId)) {
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices += "run_stage6_prerequisite_bringup_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId"
}
if (-not [string]::IsNullOrWhiteSpace($Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement)) {
  if ($Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'RequestNext') {
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices += "run_stage6_prerequisite_bringup_request_next_for_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement"
  } elseif ($Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'GrantNext') {
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices += "run_stage6_prerequisite_bringup_grant_next_for_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement"
  } elseif ($Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'ExecuteNext') {
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices += "run_stage6_prerequisite_bringup_execute_next_for_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement"
  } elseif ($Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId.StartsWith('await_')) {
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices += "run_stage6_prerequisite_bringup_approval_wait_for_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement"
  }
}
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices = [string[]]@(
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices | Sort-Object -Unique
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanNextSliceObserved = (
  @($Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices).Count -gt 0 -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanRecommendedNextSlice -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedNextSlices -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffNextStep
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedAuthorityRequired = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction -Name 'approval_action' -Default ''
)
if ([string]::IsNullOrWhiteSpace($Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedAuthorityRequired)) {
  if (
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $false) -or
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $false) -or
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction -Name 'operator_supplied_values_required' -Default $false)
  ) {
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedAuthorityRequired = 'operator_supplied_authority'
  } else {
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedAuthorityRequired = 'none_readback_only'
  }
}
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanAllowedAuthorityRequired = [string[]]@(
  'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites',
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanExpectedAuthorityRequired
) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanAuthorityObserved = (
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAllowedAuthorityRequired -contains [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAllowedAuthorityRequired -contains [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '')
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanResidentHostActionObserved = (
  (
    @(
      'request_resident_runtime_execution_authority',
      'request_host_supervision_authority'
    ) -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId -and
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'RequestNext' -and
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_operator_approval_decision' -Default $true)
  ) -or
  (
    @(
      'grant_resident_runtime_execution_authority',
      'grant_host_supervision_authority'
    ) -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId -and
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'GrantNext' -and
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $false) -and
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $false) -and
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_operator_approval_decision' -Default $false)
  ) -or
  (
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId -eq 'execute_supervised_resident_host_start' -and
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'ExecuteNext' -and
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $false) -and
    [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_operator_approval_decision' -Default $true)
  )
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceRequirements = @(
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceRequestActionObserved = (
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceRequirements -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId -eq "request_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement`_authority" -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'RequestNext' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_operator_approval_decision' -Default $true)
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceGrantActionObserved = (
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceRequirements -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId -eq "grant_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement`_authority" -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'GrantNext' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_operator_approval_decision' -Default $false)
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceExecuteActionObserved = (
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceRequirements -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId -eq "execute_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement" -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'ExecuteNext' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_operator_approval_decision' -Default $true)
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceAwaitActionObserved = (
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceRequirements -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionId -eq "await_$Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement`_authority_approval" -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommandMode -eq 'Status' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_confirmation' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_approval_id' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanCommand -Name 'requires_operator_approval_decision' -Default $false)
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionObserved = (
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanResidentHostActionObserved -or
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceRequestActionObserved -or
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceGrantActionObserved -or
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceExecuteActionObserved -or
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSurfaceAwaitActionObserved
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSource = [string](
  Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanGap = [string](
  Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffGap = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanSourceObserved = (
  (
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSource -eq 'stage6_prerequisite_bringup_operator_plan' -and
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanGap -eq 'persistent_supervision_required_prerequisites_missing' -and
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffGap -eq 'persistent_supervision_required_prerequisites_missing'
  ) -or
  (
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSource -eq 'stage6_closure_readback_summon_resident_host_blocker' -and
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanGap -eq 'summon_anywhere_blockers' -and
    $Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffGap -eq 'persistent_supervision_execution_boundary' -and
    [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'consumed_summon_anywhere_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
    [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'previous_next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit'
  )
)
$Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanSourceObserved -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanNextSliceObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status' -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAuthorityObserved -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/host/persistent-supervision' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/persistent-supervision/enablement' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAllowedRequirements -contains $Stage6CompletionAuditPrerequisiteBringupOperatorPlanEffectiveFirstMissingRequirement -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanRequirement -eq $Stage6CompletionAuditPrerequisiteBringupOperatorPlanEffectiveFirstMissingRequirement -and
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanActionObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction -Name 'method' -Default '') -eq 'POST' -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction -Name 'operator_supplied_values_required' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction -Name 'script_would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupOperatorPlanAction -Name 'script_would_mutate' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_restart_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_decide_approval' -Default $true)
)
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptAction = Get-PropertyValue `
  -Payload $Stage6CompletionAuditRecommendedHandoff `
  -Name 'next_operator_action' `
  -Default ([ordered]@{})
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptSource = [string](
  Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptGap = [string](
  Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffStatus = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'status' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffGap = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default ''
)
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptId = [string](
  Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'latest_receipt_id' -Default ''
)
if ([string]::IsNullOrWhiteSpace($Stage6CompletionAuditPrerequisiteBringupEnablementReceiptId)) {
  $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptId = [string](
    Get-PropertyValue `
      -Payload $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptAction `
      -Name 'latest_receipt_id' `
      -Default ''
  )
}
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptSourceObserved = (
  (
    $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptSource -eq 'stage6_prerequisite_bringup_enablement_receipt_review' -and
    $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptGap -eq 'persistent_supervision_execution_boundary' -and
    $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffStatus -eq 'receipt_review_ready'
  ) -or
  (
    $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptSource -eq 'stage6_prerequisite_bringup_operator_plan' -and
    $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptGap -eq 'summon_anywhere_blockers' -and
    $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffStatus -eq 'blocked'
  )
)
$Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffObserved = (
  $Stage6CompletionAuditReadbackObserved -and
  $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptSourceObserved -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '') -eq 'run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '') -eq 'none_readback_only' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $true) -and
  $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffGap -eq 'persistent_supervision_execution_boundary' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'next_step' -Default '') -eq 'run_stage6_prerequisite_bringup_review_persistent_supervision_enablement_receipt' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '') -eq '/lens/host/persistent-supervision/enablement/executions' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_required' -Default '') -eq 'none_readback_only' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  -not [string]::IsNullOrWhiteSpace($Stage6CompletionAuditPrerequisiteBringupEnablementReceiptId) -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptAction -Name 'id' -Default '') -eq 'review_persistent_supervision_enablement_receipt' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptAction -Name 'route' -Default '') -eq '/lens/host/persistent-supervision/enablement/executions' -and
  [string](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptAction -Name 'mode' -Default '') -eq 'readback' -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptAction -Name 'script_would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptAction -Name 'script_would_mutate' -Default $true) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_request_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_grant_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_decide_approval' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'would_write_memory' -Default $true)
)
$PersistentSupervisionRequiredPrerequisitesObserved = (
  @($PersistentSupervisionMissingRequiredBeforeEnable).Count -gt 0 -and
  @($PersistentSupervisionEnablementMissingRequiredBeforeEnable).Count -gt 0 -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'required_before_enable_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementReadback -Name 'required_before_enable_ready' -Default $true)
)
$PersistentSupervisionRequiredPrerequisitesHandoff = [ordered]@{}
if ($PersistentSupervisionRequiredPrerequisitesObserved) {
  $PersistentSupervisionRequiredPrerequisitesHandoff = [ordered]@{
    next_step = 'resolve_persistent_supervision_required_prerequisites_before_enablement'
    proof_script = 'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status'
    route = '/lens/host/persistent-supervision'
    readiness_route = '/lens/host/persistent-supervision/enablement'
    next_smallest_truthful_gap = 'persistent_supervision_required_prerequisites_missing'
    missing_required_before_enable = [string[]]@($PersistentSupervisionMissingRequiredBeforeEnable)
    first_missing_required_before_enable = $PersistentSupervisionFirstMissingRequiredBeforeEnable
    first_missing_requirement_handoff = $PersistentSupervisionFirstMissingRequirementHandoff
    acceptance_criterion = 'system_resident_presence'
    authority_required = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}

$FirstMissingResidentCandidateSupervised = [bool](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'resident_runtime_candidate_supervised' -Default $false
)
$SupervisionExecutionReceiptObserved = [bool](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'supervision_execution_receipt_observed' -Default $false
)
$SupervisionExecutionReceiptId = [string](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'supervision_execution_receipt_id' -Default ''
)
$CandidateObservedByFreshSupervisor = (
  $FreshResidentRuntimeCandidateSupervised -and
  $ResidentRuntimeCandidateSupervised -and
  $SupervisorFreshnessStatus -eq 'fresh'
)
$CandidateObservedByDurableReceipt = (
  $SupervisionExecutionReceiptObserved -and
  $FirstMissingResidentCandidateSupervised -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'supervision_execution_next_smallest_truthful_gap' -Default '') -eq 'resident_supervision_not_persistent'
)
$ResidentRuntimeCandidateHandoff = [ordered]@{}
$ResidentRuntimeCandidateHandoffObserved = (
  $PersistentSupervisionFirstMissingRequirementHandoffReady -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  @(
    'resident_host_process_not_supervised',
    'resident_supervision_not_persistent'
  ) -contains [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default '') -and
  ($CandidateObservedByFreshSupervisor -or $CandidateObservedByDurableReceipt)
)
if ($ResidentRuntimeCandidateHandoffObserved) {
  $ResidentRuntimeCandidateHandoff = [ordered]@{
    id = 'resident_runtime_candidate'
    status = 'observed_not_persistent'
    previous_next_smallest_truthful_gap = 'resident_host_process_not_supervised'
    next_smallest_truthful_gap = 'resident_supervision_not_persistent'
    recommended_next_slice = 'resolve_resident_supervision_persistence_before_persistent_supervision_enablement'
    proof_script = 'scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status'
    route = '/lens/host'
    readiness_route = '/lens/host/runtime-loop/readiness'
    source = $(if ($CandidateObservedByDurableReceipt) { '/lens/status resident_host.persistent_supervision_plan.first_missing_requirement_handoff.supervision_execution_receipt_observed' } else { '/lens/status resident_host.fresh_resident_runtime_candidate_supervised' })
    receipt_id = $SupervisionExecutionReceiptId
    candidate_observed_by_fresh_supervisor = $CandidateObservedByFreshSupervisor
    candidate_observed_by_supervision_execution_receipt = $CandidateObservedByDurableReceipt
    blocked_reason = 'resident_supervision_not_persistent'
    acceptance_criterion = 'system_resident_presence'
    authority_required = 'persistent_process_supervision_authority'
    authority_granted = $false
    previous_diagnostic_proof_observed = $true
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}

$CriterionNextGap = [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'next_smallest_truthful_gap' -Default '')
$FamilyNextGap = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '')
$FamilyProofScript = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'proof_script' -Default '')
$RecommendedNextGap = $FamilyNextGap
if ([string]::IsNullOrWhiteSpace($RecommendedNextGap)) {
  $RecommendedNextGap = $CriterionNextGap
}
if ([string]::IsNullOrWhiteSpace($RecommendedNextGap)) {
  $RecommendedNextGap = $StageNextGap
}

$RecommendedNextSlice = $RecommendedNextGap
$RecommendedProofScript = $FamilyProofScript
$RecommendedRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'route' -Default '')
$RecommendedReadinessRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'readiness_route' -Default '')
$AuthorityRequired = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_required' -Default '')
$AuthorityGranted = [bool](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_granted' -Default $false)
$RecommendedHandoffSource = 'first_blocker_family_handoff'

$ClosureObserved = (
  [string](Get-PropertyValue -Payload $ClosureReadback -Name 'kind' -Default '') -eq 'lens.stage6.closure_readback' -and
  [string](Get-PropertyValue -Payload $ClosureReadback -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ClosureReadback -Name 'ready_to_close' -Default $true)
)
$StageBoundaryObserved = (
  [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage' -Default '') -eq 'Stage 6 / Lens MVP' -and
  [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage_state' -Default '') -eq 'active'
)
$FirstBlockedCriterionObserved = (
  $FirstBlockedCriterionId -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'status' -Default '') -eq 'blocked'
)
$FirstFamilyHandoffObserved = (
  $FirstBlockerFamily -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'status' -Default '') -eq 'blocked' -and
  -not [string]::IsNullOrWhiteSpace($FamilyNextGap) -and
  -not [string]::IsNullOrWhiteSpace($RecommendedProofScript) -and
  -not [string]::IsNullOrWhiteSpace($RecommendedRoute)
)
$CompletionAuditHandoffObserved = (
  [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'authority_required' -Default '') -eq 'process_supervision_authority' -and
  [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'diagnostic_only' -Default $false)
)
$CompletionAuditProofScript = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'proof_script' -Default '')
$CompletionAuditNextGap = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'next_smallest_truthful_gap' -Default '')
$CompletionAuditNextStep = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'next_step' -Default '')
if (
  $CompletionAuditHandoffObserved -and
  -not [string]::IsNullOrWhiteSpace($CompletionAuditProofScript) -and
  -not [string]::IsNullOrWhiteSpace($CompletionAuditNextGap)
) {
  $RecommendedHandoffSource = 'first_blocker_family_completion_audit_handoff'
  $RecommendedNextGap = $CompletionAuditNextGap
  $RecommendedNextSlice = $CompletionAuditNextStep
  if ([string]::IsNullOrWhiteSpace($RecommendedNextSlice)) {
    $RecommendedNextSlice = $CompletionAuditNextGap
  }
  $RecommendedProofScript = $CompletionAuditProofScript
  $AuthorityRequired = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'authority_required' -Default '')
  $AuthorityGranted = [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'authority_granted' -Default $false)
}
if ($PersistentSupervisionRequiredPrerequisitesObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_required_prerequisites_handoff'
  $RecommendedNextGap = 'persistent_supervision_required_prerequisites_missing'
  $RecommendedNextSlice = 'resolve_persistent_supervision_required_prerequisites_before_enablement'
  $RecommendedProofScript = 'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status'
  $RecommendedRoute = '/lens/host/persistent-supervision'
  $RecommendedReadinessRoute = '/lens/host/persistent-supervision/enablement'
  $AuthorityRequired = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
  $AuthorityGranted = [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'authority_granted' -Default $false)
}
if ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  $FirstMissingNextGap = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default '')
  $FirstMissingNextSlice = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_step' -Default '')
  $FirstMissingProofScript = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'proof_script' -Default '')
  $FirstMissingRoute = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'route' -Default '')
  $FirstMissingReadinessRoute = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'readiness_route' -Default '')
  $FirstMissingAuthorityRequired = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_required' -Default '')
  $FirstMissingAuthorityGranted = [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_granted' -Default $false)

  if (-not [string]::IsNullOrWhiteSpace($FirstMissingNextGap)) {
    $RecommendedHandoffSource = 'persistent_supervision_first_missing_requirement_handoff'
    $RecommendedNextGap = $FirstMissingNextGap
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingNextSlice)) {
    $RecommendedNextSlice = $FirstMissingNextSlice
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingProofScript)) {
    $RecommendedProofScript = $FirstMissingProofScript
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingRoute)) {
    $RecommendedRoute = $FirstMissingRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingReadinessRoute)) {
    $RecommendedReadinessRoute = $FirstMissingReadinessRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingAuthorityRequired)) {
    $AuthorityRequired = $FirstMissingAuthorityRequired
    $AuthorityGranted = $FirstMissingAuthorityGranted
  }
}
if ($PersistentSupervisionEnablementAuthorityHandoffObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_enablement_authority_denial_handoff'
  $RecommendedNextGap = [string]$PersistentSupervisionEnablementAuthorityHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$PersistentSupervisionEnablementAuthorityHandoff.next_step
  $RecommendedProofScript = [string]$PersistentSupervisionEnablementAuthorityHandoff.proof_script
  $RecommendedRoute = [string]$PersistentSupervisionEnablementAuthorityHandoff.route
  $RecommendedReadinessRoute = [string]$PersistentSupervisionEnablementAuthorityHandoff.readiness_route
  $AuthorityRequired = [string]$PersistentSupervisionEnablementAuthorityHandoff.authority_required
  $AuthorityGranted = [bool]$PersistentSupervisionEnablementAuthorityHandoff.authority_granted
}
if ($ActivationExecutionHandoffReady) {
  $ActivationExecutionNextGap = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'next_smallest_truthful_gap' -Default '')
  $ActivationExecutionNextSlice = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'next_step' -Default '')
  $ActivationExecutionProofScript = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'proof_script' -Default '')
  $ActivationExecutionRoute = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'route' -Default '')
  $ActivationExecutionReadinessRoute = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'readiness_route' -Default '')
  $ActivationExecutionAuthorityRequired = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'authority_required' -Default '')
  $ActivationExecutionAuthorityGranted = [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'authority_granted' -Default $false)

  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionNextGap)) {
    $RecommendedHandoffSource = 'activation_execution_handoff'
    $RecommendedNextGap = $ActivationExecutionNextGap
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionNextSlice)) {
    $RecommendedNextSlice = $ActivationExecutionNextSlice
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionProofScript)) {
    $RecommendedProofScript = $ActivationExecutionProofScript
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionRoute)) {
    $RecommendedRoute = $ActivationExecutionRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionReadinessRoute)) {
    $RecommendedReadinessRoute = $ActivationExecutionReadinessRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionAuthorityRequired)) {
    $AuthorityRequired = $ActivationExecutionAuthorityRequired
    $AuthorityGranted = $ActivationExecutionAuthorityGranted
  }
}
if ($ResidentRuntimeCandidateHandoffObserved) {
  $RecommendedHandoffSource = 'resident_runtime_candidate_handoff'
  $RecommendedNextGap = 'resident_supervision_not_persistent'
  $RecommendedNextSlice = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'recommended_next_slice' -Default '')
  $RecommendedProofScript = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'proof_script' -Default '')
  $RecommendedRoute = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'route' -Default '')
  $RecommendedReadinessRoute = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'readiness_route' -Default '')
  $AuthorityRequired = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'authority_required' -Default '')
  $AuthorityGranted = [bool](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'authority_granted' -Default $false)
}
$Stage6PrerequisiteBringupCommandMode = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorCommand -Name 'mode' -Default 'Status'
)
$Stage6PrerequisiteBringupNextOperatorActionId = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'id' -Default ''
)
$Stage6PrerequisiteBringupCommandModeSlug = switch ($Stage6PrerequisiteBringupCommandMode) {
  'RequestNext' { 'request_next' }
  'GrantNext' { 'grant_next' }
  'ExecuteNext' { 'execute_next' }
  default { 'status' }
}
if ($Stage6PrerequisiteBringupNextOperatorActionId.StartsWith('await_')) {
  $Stage6PrerequisiteBringupCommandModeSlug = 'approval_wait'
}
$Stage6PrerequisiteBringupRecommendedNextStep = (
  "run_stage6_prerequisite_bringup_$Stage6PrerequisiteBringupCommandModeSlug`_for_$([string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default 'resident_host_process'))"
)
if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  $Stage6PrerequisiteBringupRecommendedNextStep = $Stage6PrerequisiteBringupNextOperatorActionId
}
$Stage6PrerequisiteBringupRecommendedNextGap = $Stage6PrerequisiteBringupPlanCurrentGap
if ($Stage6PrerequisiteBringupPlanBlockedObserved) {
  $Stage6PrerequisiteBringupRecommendedNextGap = 'persistent_supervision_required_prerequisites_missing'
}
$Stage6PrerequisiteBringupAuthorityRequired = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
$Stage6PrerequisiteBringupAuthorityGranted = $false
if ($Stage6PrerequisiteBringupPlanReadyForEnablementObserved) {
  $Stage6PrerequisiteBringupAuthorityRequired = 'persistent_supervision_enablement_sequence_authority'
}
if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  $Stage6PrerequisiteBringupAuthorityRequired = 'none_readback_only'
  $Stage6PrerequisiteBringupAuthorityGranted = $true
}
$Stage6PrerequisiteBringupOperatorPlanHandoff = [ordered]@{}
if ($Stage6PrerequisiteBringupPlanObserved) {
  $Stage6PrerequisiteBringupOperatorPlanHandoff = [ordered]@{
    status = $Stage6PrerequisiteBringupPlanStatus
    next_smallest_truthful_gap = $Stage6PrerequisiteBringupRecommendedNextGap
    next_step = $Stage6PrerequisiteBringupRecommendedNextStep
    proof_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status'
    route = '/lens/host/persistent-supervision'
    readiness_route = '/lens/host/persistent-supervision/enablement'
    operator_plan_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1'
    current_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default '')
    current_truthful_gap_basis = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap_basis' -Default '')
    current_first_missing_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_requirement' -Default '')
    current_first_missing_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
    next_operator_action_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    next_operator_actor_scope_readiness = $Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness
    operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
    required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable)
    required_before_enable_ready = [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false)
    first_missing_requirement_handoff = $(Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'first_missing_requirement_handoff' -Default ([ordered]@{}))
    authority_required = $Stage6PrerequisiteBringupAuthorityRequired
    authority_granted = $Stage6PrerequisiteBringupAuthorityGranted
    read_only_contract = $true
    diagnostic_only = $true
    plan_only = $true
    requires_explicit_operator_execution = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@(@(
        [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default ''),
        [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
      ) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique)
  }
}
if ($Stage6PrerequisiteBringupPlanObserved) {
  $RecommendedHandoffSource = 'stage6_prerequisite_bringup_operator_plan'
  $RecommendedNextGap = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.next_step
  $RecommendedProofScript = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.proof_script
  $RecommendedRoute = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.route
  $RecommendedReadinessRoute = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.readiness_route
  $AuthorityRequired = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.authority_required
  $AuthorityGranted = [bool]$Stage6PrerequisiteBringupOperatorPlanHandoff.authority_granted
}
if ($PersistentSupervisionEnablementReceiptReviewObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_enablement_receipt_review_handoff'
  $RecommendedNextGap = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.next_step
  $RecommendedProofScript = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.proof_script
  $RecommendedRoute = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.route
  $RecommendedReadinessRoute = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.readiness_route
  $AuthorityRequired = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.authority_required
  $AuthorityGranted = [bool]$PersistentSupervisionEnablementReceiptReviewHandoff.authority_granted
}
if ($PersistentSupervisionResidentClaimBoundaryHandoffObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_resident_claim_boundary_handoff'
  $RecommendedNextGap = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.next_step
  $RecommendedProofScript = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.proof_script
  $RecommendedRoute = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.route
  $RecommendedReadinessRoute = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.readiness_route
  $AuthorityRequired = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.authority_required
  $AuthorityGranted = [bool]$PersistentSupervisionResidentClaimBoundaryHandoff.authority_granted
}
$Stage6CompletionAuditHandoffConsumedByClosureReadback = (
  $PersistentSupervisionResidentClaimBoundaryHandoffObserved -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  $StageNextGap -eq 'summon_anywhere_blockers' -and
  $FirstBlockedCriterionObserved
)
$Stage6CompletionAuditRecommendedHandoffConsumed = (
  $Stage6CompletionAuditHelpfulNotNoisyRuntimeAuthorityHandoffObserved -or
  $Stage6CompletionAuditHelpfulNotNoisyResidentSurfaceRuntimeHandoffObserved -or
  $Stage6CompletionAuditSummonApiLaunchOnHotkeyReadbackHandoffObserved -or
  $Stage6CompletionAuditResidentRuntimeTrayPresenceHandoffObserved -or
  $Stage6CompletionAuditPersistentSupervisionApiExecutionHandoffObserved -or
  $Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryHandoffObserved -or
  $Stage6CompletionAuditReviewedSummonFirstBlockerHandoffObserved -or
  $Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementHandoffObserved -or
  $Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffObserved -or
  (
    $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffObserved -and
    (
      -not $PersistentSupervisionResidentClaimBoundaryHandoffObserved -or
      $Stage6CompletionAuditLaunchOnHotkeyRuntimeReadbackObserved
    )
  )
)
if ($Stage6CompletionAuditRecommendedHandoffConsumed) {
  $RecommendedHandoffSource = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '')
  $RecommendedNextGap = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '')
  $RecommendedNextSlice = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '')
  $RecommendedProofScript = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '')
  $RecommendedRoute = [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'route' -Default '')
  $RecommendedReadinessRoute = [string](Get-PropertyValue -Payload $Stage6CompletionAuditRecommendedHandoff -Name 'readiness_route' -Default '')
  $AuthorityRequired = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '')
  $AuthorityGranted = [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $false)
}
$Stage6CompletionAuditRuntimeReadbackRequired = (
  $Stage6CompletionAuditHandoffConsumedByClosureReadback -and
  -not $Stage6CompletionAuditRecommendedHandoffConsumed -and
  -not $Stage6CompletionAuditLaunchOnHotkeyRuntimeReadbackObserved
)
if ($Stage6CompletionAuditRuntimeReadbackRequired) {
  $RecommendedHandoffSource = 'stage6_completion_audit_launch_on_hotkey_readback_required'
  $RecommendedNextGap = 'stage6_lens_completion_audit_runtime_readback'
  $RecommendedNextSlice = 'run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback'
  $RecommendedProofScript = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey'
  $RecommendedRoute = '/lens/status'
  $RecommendedReadinessRoute = '/lens/resident-runtime/authority-grant/readiness'
  $AuthorityRequired = 'launch_on_hotkey_runtime_readback_opt_in'
  $AuthorityGranted = $false
}
$RecommendedHandoff = [ordered]@{}
if ($Stage6CompletionAuditRecommendedHandoffConsumed) {
  $RecommendedHandoff = $Stage6CompletionAuditRecommendedHandoff
} elseif ($Stage6CompletionAuditRuntimeReadbackRequired) {
  $RecommendedHandoff = [ordered]@{
    status = 'runtime_readback_required'
    previous_next_smallest_truthful_gap = 'stage6_lens_completion_audit'
    previous_closure_readback_next_smallest_truthful_gap = 'summon_anywhere_blockers'
    next_smallest_truthful_gap = 'stage6_lens_completion_audit_runtime_readback'
    next_step = 'run_stage6_completion_audit_with_launch_on_hotkey_runtime_readback'
    proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey'
    route = '/lens/status'
    readiness_route = '/lens/resident-runtime/authority-grant/readiness'
    acceptance_criterion = 'helpful_not_noisy'
    first_blocker_family = $FirstBlockerFamily
    first_blocker_family_handoff = $FirstBlockerFamilyHandoff
    first_blocker_family_completion_audit_handoff = $FirstFamilyCompletionAuditHandoff
    authority_required = 'launch_on_hotkey_runtime_readback_opt_in'
    authority_granted = $false
    requires_explicit_operator_opt_in = $true
    consumes_completion_audit_when_supplied = $true
    completion_audit_json_parameter = '-CompletionAuditJsonPath'
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    would_launch_process = $false
    would_supervise_process = $false
    would_register_hotkey = $false
    would_control_overlay = $false
    would_summon = $false
    would_decide_approval = $false
    blockers = [string[]]@(
      ConvertTo-StringArray -Value (Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'blockers')
    )
  }
} elseif ($PersistentSupervisionResidentClaimBoundaryHandoffObserved) {
  $RecommendedHandoff = $PersistentSupervisionResidentClaimBoundaryHandoff
} elseif ($PersistentSupervisionEnablementReceiptReviewObserved) {
  $RecommendedHandoff = $PersistentSupervisionEnablementReceiptReviewHandoff
} elseif ($Stage6PrerequisiteBringupPlanObserved) {
  $RecommendedHandoff = $Stage6PrerequisiteBringupOperatorPlanHandoff
} elseif ($ResidentRuntimeCandidateHandoffObserved) {
  $RecommendedHandoff = $ResidentRuntimeCandidateHandoff
} elseif ($ActivationExecutionHandoffReady) {
  $RecommendedHandoff = $ActivationExecutionHandoff
} elseif ($PersistentSupervisionEnablementAuthorityHandoffObserved) {
  $RecommendedHandoff = $PersistentSupervisionEnablementAuthorityHandoff
} elseif ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  $RecommendedHandoff = $PersistentSupervisionFirstMissingRequirementHandoff
} elseif ($PersistentSupervisionRequiredPrerequisitesObserved) {
  $RecommendedHandoff = $PersistentSupervisionRequiredPrerequisitesHandoff
} elseif ($CompletionAuditHandoffObserved) {
  $RecommendedHandoff = $FirstFamilyCompletionAuditHandoff
} elseif ($FirstFamilyHandoffObserved) {
  $RecommendedHandoff = $FirstBlockerFamilyHandoff
}

$RecommendedConcreteHandoffSource = $RecommendedHandoffSource
$RecommendedConcreteHandoff = $RecommendedHandoff
$RecommendedConcreteNextSlice = [string](
  Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'next_step' -Default $RecommendedNextSlice
)
$RecommendedConcreteProofScript = [string](
  Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'proof_script' -Default $RecommendedProofScript
)
$RecommendedConcreteNextGap = [string](
  Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'next_smallest_truthful_gap' -Default $RecommendedNextGap
)
$RecommendedConcreteAuthorityRequired = [string](
  Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'authority_required' -Default $AuthorityRequired
)
$RecommendedConcreteAuthorityGranted = [bool](
  Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'authority_granted' -Default $AuthorityGranted
)
$RecommendedConcreteExecutionHandoffObserved = (
  $Stage6CompletionAuditPersistentSupervisionApiExecutionHandoffObserved -and
  -not [string]::IsNullOrWhiteSpace($RecommendedConcreteNextSlice) -and
  -not [string]::IsNullOrWhiteSpace($RecommendedConcreteProofScript) -and
  [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_execute' -Default $false) -and
  [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_claim_resident' -Default $true)
)
$RecommendedConcreteSummonLaunchReadbackHandoffObserved = (
  $Stage6CompletionAuditSummonApiLaunchOnHotkeyReadbackHandoffObserved -and
  -not [string]::IsNullOrWhiteSpace($RecommendedConcreteNextSlice) -and
  -not [string]::IsNullOrWhiteSpace($RecommendedConcreteProofScript) -and
  [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_execute' -Default $false) -and
  [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_claim_resident' -Default $true)
)
$ConcreteHandoffObserved = (
  -not $Stage6CompletionAuditHandoffConsumedByClosureReadback -or
  $RecommendedConcreteExecutionHandoffObserved -or
  $RecommendedConcreteSummonLaunchReadbackHandoffObserved -or
  (
    -not [string]::IsNullOrWhiteSpace($RecommendedConcreteNextSlice) -and
    -not [string]::IsNullOrWhiteSpace($RecommendedConcreteProofScript) -and
    [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'read_only_contract' -Default $false) -and
    [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'diagnostic_only' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_execute' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'would_mutate' -Default $true)
  )
)

$RecommendedOperatorHandoff = [ordered]@{
  source = 'stage6_prerequisite_bringup_plan'
  status = if ($Stage6PrerequisiteBringupPlanObserved) { 'operator_plan_readback_ready' } else { 'operator_plan_missing' }
  next_operator_action_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
  next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
  next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
  next_operator_actor_scope_readiness = $Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness
  operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
  read_only_contract = $true
  diagnostic_only = $true
  approval_request_write_if_run = $false
  approval_decision_authority = $false
  would_execute = $false
  would_mutate = $false
}
if ($Stage6CompletionAuditRuntimeReadbackRequired) {
  $RecommendedOperatorHandoff = New-Stage6CompletionAuditRuntimeOperatorHandoff
} elseif (
  $Stage6CompletionAuditRecommendedHandoffConsumed -and
  $RecommendedNextSlice -eq 'create_or_select_exact_approved_resident_runtime_execution_authority_request'
) {
  $RecommendedOperatorHandoff = New-ResidentRuntimeAuthorityRequestOperatorHandoff `
    -SourceHandoff $RecommendedHandoff `
    -ResidentRuntimeAuthorityRequests $ResidentRuntimeAuthorityRequests `
    -ResidentRuntimeAuthorityGrants $ResidentRuntimeAuthorityGrants `
    -CompletionAuditJsonPath $ResolvedCompletionAuditJsonPath
} elseif ($Stage6CompletionAuditRecommendedHandoffConsumed) {
  $RecommendedOperatorHandoff = New-Stage6CompletionAuditReadbackOperatorHandoff `
    -RecommendedHandoff $RecommendedHandoff `
    -RecommendedNextSlice $RecommendedNextSlice `
    -RecommendedProofScript $RecommendedProofScript `
    -RecommendedRoute $RecommendedRoute `
    -RecommendedReadinessRoute $RecommendedReadinessRoute `
    -AuthorityRequired $AuthorityRequired `
    -AuthorityGranted $AuthorityGranted
}
$RecommendedOperatorActionRequirement = [string](
  Get-PropertyValue -Payload $RecommendedOperatorHandoff -Name 'next_operator_action_requirement' -Default ''
)
$RecommendedOperatorAction = Get-PropertyValue `
  -Payload $RecommendedOperatorHandoff `
  -Name 'next_operator_action' `
  -Default ([ordered]@{})
$RecommendedOperatorCommand = Get-PropertyValue `
  -Payload $RecommendedOperatorHandoff `
  -Name 'next_operator_command' `
  -Default ([ordered]@{})
$RecommendedOperatorActorScopeReadiness = Get-PropertyValue `
  -Payload $RecommendedOperatorHandoff `
  -Name 'next_operator_actor_scope_readiness' `
  -Default ([ordered]@{})
$RecommendedOperatorSequenceCommandAvailability = Get-PropertyValue `
  -Payload $RecommendedOperatorHandoff `
  -Name 'operator_sequence_command_availability' `
  -Default ([ordered]@{})
$RecommendedOperatorHandoffStatus = [string](
  Get-PropertyValue -Payload $RecommendedOperatorHandoff -Name 'status' -Default ''
)
if (
  $Stage6CompletionAuditRecommendedHandoffConsumed -and
  $RecommendedOperatorHandoffStatus -eq 'authority_grant_receipt_already_active'
) {
  $RecommendedNextSlice = 'review_resident_runtime_execution_authority_grant_receipt'
  $RecommendedProofScript = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status'
  $RecommendedRoute = '/lens/resident-runtime/authority-grant/grants'
  $RecommendedReadinessRoute = '/lens/resident-runtime/authority-grant/readiness'
  $AuthorityRequired = 'none_readback_only'
  $AuthorityGranted = $true
}

$RecommendedFirstMissingAuthorityRequired = [string](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_required' -Default ''
)
$FirstMissingHandoffNextGap = [string](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default ''
)
if ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  if ($FirstMissingHandoffNextGap -eq 'resident_host_process_not_supervised') {
    $RecommendedFirstMissingAuthorityRequired = 'process_supervision_authority'
  } elseif ($FirstMissingHandoffNextGap -eq 'resident_supervision_not_persistent') {
    $RecommendedFirstMissingAuthorityRequired = 'persistent_process_supervision_authority'
  }
}
$FamilyChainHandoffObserved = (
  [string](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'authority_required' -Default '') -eq 'resident_runtime_execution_authority' -and
  [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'diagnostic_only' -Default $false)
)
$SideEffectsDenied = (
  -not [bool](Get-PropertyValue -Payload $CriterionHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $CriterionHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupOperatorPlanHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupOperatorPlanHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementReceiptReviewHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementReceiptReviewHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_mutate' -Default $false)
)
$PersistentSupervisionRequiredPrerequisitesCheckPassed = (
  $PersistentSupervisionRequiredPrerequisitesObserved -or
  $Stage6PrerequisiteBringupPlanReadyForEnablementObserved -or
  $Stage6PrerequisiteBringupPlanAppliedObserved
)
$PersistentSupervisionRequiredPrerequisitesCheckStatus = if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  'not_applicable_enablement_applied'
} elseif ($PersistentSupervisionRequiredPrerequisitesObserved) {
  'required_prerequisites_handoff_ready'
} elseif ($Stage6PrerequisiteBringupPlanReadyForEnablementObserved) {
  'not_applicable_prerequisites_ready'
} else {
  'missing_or_unexpected'
}
$PersistentSupervisionFirstMissingRequirementCheckPassed = (
  $PersistentSupervisionFirstMissingRequirementHandoffReady -or
  $Stage6PrerequisiteBringupPlanReadyForEnablementObserved -or
  $Stage6PrerequisiteBringupPlanAppliedObserved
)
$PersistentSupervisionFirstMissingRequirementCheckStatus = if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  'not_applicable_enablement_applied'
} elseif ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  'first_missing_requirement_handoff_ready'
} elseif ($Stage6PrerequisiteBringupPlanReadyForEnablementObserved) {
  'not_applicable_prerequisites_ready'
} else {
  'missing_or_unexpected'
}

$Checks = @(
  New-Check -Id 'closure_readback' -Status 'blocked_closure_readback_observed' -Passed $ClosureObserved -Evidence '/lens/status stage6_readiness.closure_readback' -Reason 'Stage 6 closure must remain blocked before transition.'
  New-Check -Id 'stage_boundary' -Status 'stage6_active' -Passed $StageBoundaryObserved -Evidence '/lens/status stage6_readiness' -Reason 'The next handoff only applies while Stage 6 is active.'
  New-Check -Id 'first_blocked_criterion' -Status 'summon_anywhere_blocked' -Passed $FirstBlockedCriterionObserved -Evidence 'closure_readback.blocked_criteria[0]' -Reason 'Summon-anywhere is still the first blocked acceptance criterion.'
  New-Check -Id 'first_blocker_family_handoff' -Status 'resident_host_handoff_ready' -Passed $FirstFamilyHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_handoff' -Reason 'The next concrete handoff points at the resident host runtime boundary.'
  New-Check -Id 'completion_audit_handoff' -Status 'process_supervision_audit_handoff_ready' -Passed $CompletionAuditHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_completion_audit_handoff' -Reason 'The process-supervision handoff is present but diagnostic-only.'
  New-Check -Id 'family_chain_handoff' -Status 'summon_family_chain_handoff_ready' -Passed $FamilyChainHandoffObserved -Evidence 'summon_anywhere.handoff.summon_anywhere_family_chain_completion_audit_handoff' -Reason 'The summon blocker family chain can still be consumed by audit.'
  New-Check -Id 'concrete_handoff' -Status $(if ($ConcreteHandoffObserved) { 'concrete_handoff_ready' } else { 'missing_or_unexpected' }) -Passed $ConcreteHandoffObserved -Evidence 'recommended_concrete_handoff' -Reason 'The broad closure blocker must also expose the concrete diagnostic handoff an operator can run next.'
  New-Check -Id 'persistent_supervision_required_prerequisites' -Status $PersistentSupervisionRequiredPrerequisitesCheckStatus -Passed $PersistentSupervisionRequiredPrerequisitesCheckPassed -Evidence '/lens/status resident_host.persistent_supervision_plan missing_required_before_enable' -Reason 'The latest Stage 6 handoff must preserve the full persistent-supervision prerequisite map after the audit chain consumes the older resident-host proofs, or explicitly report that the prerequisite chain is already ready/applied.'
  New-Check -Id 'persistent_supervision_first_missing_requirement' -Status $PersistentSupervisionFirstMissingRequirementCheckStatus -Passed $PersistentSupervisionFirstMissingRequirementCheckPassed -Evidence '/lens/status resident_host.persistent_supervision_plan first_missing_requirement_handoff' -Reason 'The persistent-supervision prerequisite gap must name the first concrete missing prerequisite before the next slice, unless the governed bring-up plan has already advanced beyond missing prerequisites.'
  New-Check -Id 'stage6_prerequisite_bringup_plan' -Status $(if ($Stage6PrerequisiteBringupPlanObserved) { 'operator_plan_readback_ready' } else { 'missing_or_unexpected' }) -Passed $Stage6PrerequisiteBringupPlanObserved -Evidence 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status' -Reason 'The next handoff should point at the governed prerequisite bring-up runbook instead of lower-level proof fragments.'
  New-Check -Id 'persistent_supervision_enablement_receipt_review' -Status $(if ($PersistentSupervisionEnablementReceiptReviewObserved) { 'receipt_reviewed' } elseif ($Stage6PrerequisiteBringupPlanAppliedObserved) { 'missing_or_unexpected' } else { 'not_applicable' }) -Passed $(-not $Stage6PrerequisiteBringupPlanAppliedObserved -or $PersistentSupervisionEnablementReceiptReviewObserved) -Evidence '/lens/status resident_host.persistent_supervision_enablement_execution_receipts' -Reason 'After enablement is applied, the next handoff must consume the read-only receipt review before advancing to resident-claim boundary review.'
  New-Check -Id 'persistent_supervision_resident_claim_boundary_review' -Status $(if ($PersistentSupervisionResidentClaimBoundaryHandoffObserved) { 'resident_claim_boundary_consumed' } elseif ($PersistentSupervisionEnablementReceiptReviewObserved) { 'missing_or_unexpected' } else { 'not_applicable' }) -Passed $(-not $PersistentSupervisionEnablementReceiptReviewObserved -or $PersistentSupervisionResidentClaimBoundaryHandoffObserved) -Evidence 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status' -Reason 'After enablement receipt review, the next handoff must consume the read-only resident-claim boundary before routing to the Stage 6 completion audit.'
  New-Check -Id 'stage6_completion_audit_runtime_authority_handoff' -Status $(if ($Stage6CompletionAuditHelpfulNotNoisyRuntimeAuthorityHandoffObserved) { 'runtime_authority_handoff_consumed' } elseif ($Stage6CompletionAuditRecommendedHandoffConsumed) { 'completion_audit_recommended_handoff_consumed' } elseif ($Stage6CompletionAuditReadbackObserved) { 'completion_audit_readback_observed' } elseif ($Stage6CompletionAuditRuntimeReadbackRequired) { 'runtime_readback_required' } else { 'not_requested' }) -Passed $([string]::IsNullOrWhiteSpace($CompletionAuditJsonPath) -or $Stage6CompletionAuditReadbackObserved) -Evidence 'scripts/lens-stage6-completion-audit.ps1 -Mode Status -AllowLaunchOnHotkey or -CompletionAuditJsonPath <audit.json>' -Reason 'When Stage 6 closure readback reaches the completion-audit boundary, the next handoff should require the explicit launch-on-hotkey audit readback or consume a supplied completion-audit JSON payload instead of falling back to stale closure readback.'
  New-Check -Id 'persistent_supervision_enablement_authority_handoff' -Status $(if ($PersistentSupervisionEnablementAuthorityHandoffObserved) { 'enablement_authority_handoff_ready' } else { 'not_observed' }) -Passed $true -Evidence '/lens/status resident_host.persistent_supervision_enablement_authority_readiness' -Reason 'When the enablement authority denial and execution-denial readiness are already audited, the next handoff can point at the enablement-authority proof without granting authority.'
  New-Check -Id 'activation_execution_handoff' -Status $(if ($ActivationExecutionHandoffReady) { 'activation_execution_handoff_ready' } else { 'not_observed' }) -Passed $true -Evidence '/lens/status resident_host.activation_state latest_execution_handoff' -Reason 'When a bounded activation execution receipt exists, the handoff can point directly at process-supervision proof without claiming resident host status.'
  New-Check -Id 'resident_runtime_candidate_handoff' -Status $(if ($ResidentRuntimeCandidateHandoffObserved -and $CandidateObservedByDurableReceipt) { 'receipt_candidate_handoff_ready' } elseif ($ResidentRuntimeCandidateHandoffObserved) { 'fresh_candidate_handoff_ready' } else { 'not_observed' }) -Passed $true -Evidence '/lens/status resident_host resident candidate readback' -Reason 'When a fresh or receipt-backed supervised resident candidate is present, the handoff can point at persistence; otherwise it remains on the first missing resident-host prerequisite.'
  New-Check -Id 'side_effects_denied' -Status 'readback_only' -Passed $SideEffectsDenied -Evidence 'handoff governance flags' -Reason 'The handoff script must not grant or imply execution authority.'
)
$Ok = -not @($Checks | Where-Object { -not [bool](Get-PropertyValue -Payload $_ -Name 'passed' -Default $false) })

$Payload = [ordered]@{
  kind = 'lens.stage6.next_handoff.proof'
  status = if ($Ok) { 'proof_passed' } else { 'blocked' }
  ok = $Ok
  mode = $Mode.ToLowerInvariant()
  stage = [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage' -Default '')
  stage_state = [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage_state' -Default '')
  ready_to_close = [bool](Get-PropertyValue -Payload $ClosureReadback -Name 'ready_to_close' -Default $false)
  stage_next_smallest_truthful_gap = $StageNextGap
  next_smallest_truthful_gap = $RecommendedNextGap
  acceptance_criterion = $FirstBlockedCriterionId
  acceptance_criterion_status = [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'status' -Default '')
  criterion_next_smallest_truthful_gap = $CriterionNextGap
  first_blocker_family = $FirstBlockerFamily
  first_blocker_family_next_smallest_truthful_gap = $FamilyNextGap
  recommended_next_slice = $RecommendedNextSlice
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_handoff = $RecommendedHandoff
  recommended_concrete_handoff_source = $RecommendedConcreteHandoffSource
  recommended_concrete_handoff = $RecommendedConcreteHandoff
  recommended_concrete_next_slice = $RecommendedConcreteNextSlice
  recommended_concrete_proof_script = $RecommendedConcreteProofScript
  recommended_concrete_next_smallest_truthful_gap = $RecommendedConcreteNextGap
  recommended_concrete_authority_required = $RecommendedConcreteAuthorityRequired
  recommended_concrete_authority_granted = $RecommendedConcreteAuthorityGranted
  recommended_proof_script = $RecommendedProofScript
  recommended_route = $RecommendedRoute
  recommended_readiness_route = $RecommendedReadinessRoute
  authority_required = $AuthorityRequired
  authority_granted = $AuthorityGranted
  stage6_prerequisite_bringup_plan_observed = $Stage6PrerequisiteBringupPlanObserved
  stage6_prerequisite_bringup_operator_plan_handoff = $Stage6PrerequisiteBringupOperatorPlanHandoff
  persistent_supervision_enablement_receipt_review_handoff_observed = $PersistentSupervisionEnablementReceiptReviewObserved
  persistent_supervision_enablement_receipt_review_handoff = $PersistentSupervisionEnablementReceiptReviewHandoff
  persistent_supervision_resident_claim_boundary_handoff_observed = $PersistentSupervisionResidentClaimBoundaryHandoffObserved
  persistent_supervision_resident_claim_boundary_handoff = $PersistentSupervisionResidentClaimBoundaryHandoff
  stage6_completion_audit_handoff_consumed_by_closure_readback = $Stage6CompletionAuditHandoffConsumedByClosureReadback
  stage6_completion_audit_readback_observed = $Stage6CompletionAuditReadbackObserved
  stage6_completion_audit_launch_on_hotkey_runtime_readback_observed = $Stage6CompletionAuditLaunchOnHotkeyRuntimeReadbackObserved
  stage6_completion_audit_runtime_authority_handoff_observed = $Stage6CompletionAuditHelpfulNotNoisyRuntimeAuthorityHandoffObserved
  stage6_completion_audit_resident_surface_runtime_handoff_observed = $Stage6CompletionAuditHelpfulNotNoisyResidentSurfaceRuntimeHandoffObserved
  stage6_completion_audit_summon_api_launch_on_hotkey_readback_handoff_observed = $Stage6CompletionAuditSummonApiLaunchOnHotkeyReadbackHandoffObserved
  stage6_completion_audit_resident_runtime_tray_presence_handoff_observed = $Stage6CompletionAuditResidentRuntimeTrayPresenceHandoffObserved
  stage6_completion_audit_persistent_supervision_api_execution_handoff_observed = $Stage6CompletionAuditPersistentSupervisionApiExecutionHandoffObserved
  stage6_completion_audit_persistent_supervision_resident_claim_boundary_handoff_observed = $Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryHandoffObserved
  stage6_completion_audit_reviewed_summon_first_blocker_handoff_observed = $Stage6CompletionAuditReviewedSummonFirstBlockerHandoffObserved
  stage6_completion_audit_persistent_supervision_first_missing_requirement_handoff_observed = $Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementHandoffObserved
  stage6_completion_audit_prerequisite_bringup_operator_plan_handoff_observed = $Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffObserved
  stage6_completion_audit_enablement_receipt_review_handoff_observed = $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffObserved
  stage6_completion_audit_recommended_handoff_consumed = $Stage6CompletionAuditRecommendedHandoffConsumed
  stage6_completion_audit_runtime_readback_required = $Stage6CompletionAuditRuntimeReadbackRequired
  stage6_completion_audit_json_path_supplied = -not [string]::IsNullOrWhiteSpace($CompletionAuditJsonPath)
  stage6_completion_audit = [ordered]@{
    status = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'status' -Default '')
    audit_status = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'audit_status' -Default '')
    ok = $Stage6CompletionAuditReadbackObserved
    exit_code = [int](Get-PropertyValue -Payload $Stage6CompletionAuditResult -Name 'exit_code' -Default 0)
    allow_launch_on_hotkey = [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'allow_launch_on_hotkey' -Default $false)
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'next_smallest_truthful_gap' -Default '')
    recommended_handoff_source = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_handoff_source' -Default '')
    recommended_next_slice = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_next_slice' -Default '')
    recommended_proof_script = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'recommended_proof_script' -Default '')
    authority_required = [string](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_required' -Default '')
    authority_granted = [bool](Get-PropertyValue -Payload $Stage6CompletionAudit -Name 'authority_granted' -Default $false)
  }
  persistent_supervision_resident_claim_boundary_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'status' -Default '')
    ok = [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'ok' -Default $false)
    exit_code = [int](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryResult -Name 'exit_code' -Default 0)
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'next_smallest_truthful_gap' -Default '')
    recommended_next_slice = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_next_slice' -Default '')
    recommended_proof_script = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_proof_script' -Default '')
  }
  next_operator_action_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
  next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
  next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
  next_operator_actor_scope_readiness = $Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness
  operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
  recommended_operator_handoff = $RecommendedOperatorHandoff
  recommended_next_operator_action_requirement = $RecommendedOperatorActionRequirement
  recommended_next_operator_action = $RecommendedOperatorAction
  recommended_next_operator_command = $RecommendedOperatorCommand
  recommended_next_operator_actor_scope_readiness = $RecommendedOperatorActorScopeReadiness
  recommended_operator_sequence_command_availability = $RecommendedOperatorSequenceCommandAvailability
  recommended_prerequisites_handoff_source = $(if ($PersistentSupervisionRequiredPrerequisitesObserved) { 'persistent_supervision_required_prerequisites_handoff' } else { '' })
  recommended_prerequisites_next_slice = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'next_step' -Default '')
  recommended_prerequisites_proof_script = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'proof_script' -Default '')
  recommended_prerequisites_route = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'route' -Default '')
  recommended_prerequisites_readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'readiness_route' -Default '')
  recommended_prerequisites_authority_required = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'authority_required' -Default '')
  recommended_prerequisites_authority_granted = [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'authority_granted' -Default $false)
  recommended_first_missing_handoff_source = $(if ($PersistentSupervisionFirstMissingRequirementHandoffReady) { 'persistent_supervision_first_missing_requirement_handoff' } else { '' })
  recommended_first_missing_next_slice = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_step' -Default '')
  recommended_first_missing_proof_script = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'proof_script' -Default '')
  recommended_first_missing_route = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'route' -Default '')
  recommended_first_missing_readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'readiness_route' -Default '')
  recommended_first_missing_authority_required = $RecommendedFirstMissingAuthorityRequired
  recommended_first_missing_authority_granted = [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_granted' -Default $false)
  blocked_criteria = $BlockedCriteria
  ready_criteria = $ReadyCriteria
  first_blocker_family_handoff = $FirstBlockerFamilyHandoff
  first_blocker_family_completion_audit_handoff = $FirstFamilyCompletionAuditHandoff
  summon_anywhere_family_chain_completion_audit_handoff = $FamilyChainCompletionAuditHandoff
  persistent_supervision_required_prerequisites_observed = $PersistentSupervisionRequiredPrerequisitesObserved
  persistent_supervision_missing_required_before_enable = [string[]]@($PersistentSupervisionMissingRequiredBeforeEnable)
  persistent_supervision_first_missing_required_before_enable = $PersistentSupervisionFirstMissingRequiredBeforeEnable
  persistent_supervision_first_missing_requirement_handoff = $PersistentSupervisionFirstMissingRequirementHandoff
  persistent_supervision_required_prerequisites_handoff = $PersistentSupervisionRequiredPrerequisitesHandoff
  persistent_supervision_enablement_authority_handoff_observed = $PersistentSupervisionEnablementAuthorityHandoffObserved
  persistent_supervision_enablement_authority_handoff = $PersistentSupervisionEnablementAuthorityHandoff
  stage6_prerequisite_bringup_plan = [ordered]@{
    status = if ($Stage6PrerequisiteBringupPlanObserved) { [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'status' -Default '') } else { 'missing_or_failed' }
    ok = $Stage6PrerequisiteBringupPlanObserved
    exit_code = [int]$Stage6PrerequisiteBringupPlanResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'evidence'))
    current_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default '')
    current_truthful_gap_basis = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap_basis' -Default '')
    current_first_missing_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_requirement' -Default '')
    current_first_missing_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
    required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable)
    required_before_enable_ready = [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false)
    next_operator_action_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    next_operator_actor_scope_readiness = $Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness
    operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
    governance = $Stage6PrerequisiteBringupPlanGovernance
  }
  latest_activation_execution_handoff_observed = $ActivationExecutionHandoffReady
  latest_activation_execution_handoff = $(if ($ActivationExecutionHandoffReady) { $ActivationExecutionHandoff } else { [ordered]@{} })
  activation_execution_handoff_observed = $ActivationExecutionHandoffReady
  activation_execution_handoff = $(if ($ActivationExecutionHandoffReady) { $ActivationExecutionHandoff } else { [ordered]@{} })
  resident_runtime_candidate_handoff_observed = $ResidentRuntimeCandidateHandoffObserved
  resident_runtime_candidate_handoff = $ResidentRuntimeCandidateHandoff
  checks = $Checks
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    launch_on_hotkey_runtime_readback_opt_in = $false
    uses_lens_status_readback = $true
    uses_persistent_supervision_readback = $true
    uses_stage6_prerequisite_bringup_plan_readback = $true
    uses_stage6_completion_audit_readback = $Stage6CompletionAuditReadbackObserved
    stage6_prerequisite_bringup_plan_readback = $Stage6PrerequisiteBringupPlanObserved
    stage6_prerequisite_bringup_actor_scope_readback = [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'actor_scope_readback' -Default $false)
    stage6_completion_audit_runtime_authority_handoff_observed = $Stage6CompletionAuditHelpfulNotNoisyRuntimeAuthorityHandoffObserved
    stage6_completion_audit_resident_surface_runtime_handoff_observed = $Stage6CompletionAuditHelpfulNotNoisyResidentSurfaceRuntimeHandoffObserved
    stage6_completion_audit_resident_runtime_tray_presence_handoff_observed = $Stage6CompletionAuditResidentRuntimeTrayPresenceHandoffObserved
    stage6_completion_audit_persistent_supervision_api_execution_handoff_observed = $Stage6CompletionAuditPersistentSupervisionApiExecutionHandoffObserved
    stage6_completion_audit_persistent_supervision_resident_claim_boundary_handoff_observed = $Stage6CompletionAuditPersistentSupervisionResidentClaimBoundaryHandoffObserved
    stage6_completion_audit_persistent_supervision_first_missing_requirement_handoff_observed = $Stage6CompletionAuditPersistentSupervisionFirstMissingRequirementHandoffObserved
    stage6_completion_audit_prerequisite_bringup_operator_plan_handoff_observed = $Stage6CompletionAuditPrerequisiteBringupOperatorPlanHandoffObserved
    stage6_completion_audit_enablement_receipt_review_handoff_observed = $Stage6CompletionAuditPrerequisiteBringupEnablementReceiptHandoffObserved
    stage6_completion_audit_recommended_handoff_consumed = $Stage6CompletionAuditRecommendedHandoffConsumed
    stage6_completion_audit_runtime_readback_required = $Stage6CompletionAuditRuntimeReadbackRequired
    stage6_completion_audit_json_path_supplied = -not [string]::IsNullOrWhiteSpace($CompletionAuditJsonPath)
    proof_script = 'scripts/lens-stage6-next-handoff.ps1 -Mode Status'
    would_execute = $false
    would_mutate = $false
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    approval_request_write = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 24
if ($Ok) {
  exit 0
}
exit 1
