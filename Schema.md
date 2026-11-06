## Table `purchase_orders`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `po_number` | `text` |  |
| `company_name` | `text` |  |
| `order_date` | `text` |  Nullable |
| `created_at` | `timestamptz` |  |
| `file_path` | `text` |  Nullable |

## Table `inventory`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `item_code` | `text` |  Unique |
| `description` | `text` |  Nullable |
| `stock_qty` | `int4` |  |
| `unit` | `text` |  |
| `updated_at` | `timestamptz` |  |
| `created_at` | `timestamptz` |  |

## Table `part_vendors`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary |
| `part_code` | `text` |  |
| `vendor_name` | `text` |  |
| `vendor_type` | `text` |  |
| `created_at` | `timestamptz` |  Nullable |

## Table `tasks`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `task_id` | `text` | Primary |
| `date` | `text` |  Nullable |
| `description` | `text` |  Nullable |
| `assigned_to` | `text` |  Nullable |
| `assigned_by` | `text` |  Nullable |
| `department` | `text` |  Nullable |
| `deadline` | `text` |  Nullable |
| `priority` | `text` |  Nullable |
| `status` | `text` |  Nullable |
| `reason` | `text` |  Nullable |
| `source` | `text` |  Nullable |
| `updated_by` | `text` |  Nullable |
| `last_updated` | `timestamptz` |  Nullable |
| `checklist` | `jsonb` |  Nullable |
| `workflow_id` | `uuid` |  Nullable |
| `stage_order` | `int4` |  Nullable |
| `duration_value` | `int4` |  Nullable |
| `duration_unit` | `text` |  Nullable |
| `start_at` | `timestamptz` |  Nullable |
| `actual_start_at` | `timestamptz` |  Nullable |
| `actual_completion_at` | `timestamptz` |  Nullable |
| `progress_percentage` | `int4` |  Nullable |
| `delay_reason` | `text` |  Nullable |
| `handover_status` | `text` |  Nullable |

## Table `monthly_goals`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `goal_id` | `text` | Primary |
| `time_frame` | `text` |  Nullable |
| `week_month` | `text` |  Nullable |
| `assigned_to` | `text` |  Nullable |
| `given_by` | `text` |  Nullable |
| `goal` | `text` |  Nullable |
| `deadline` | `text` |  Nullable |
| `status` | `text` |  Nullable |
| `reason` | `text` |  Nullable |
| `updated_by` | `text` |  Nullable |
| `last_updated` | `timestamptz` |  Nullable |

## Table `extension_requests`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `request_id` | `uuid` | Primary |
| `task_id` | `text` |  Nullable |
| `task_description` | `text` |  Nullable |
| `employee_name` | `text` |  Nullable |
| `department` | `text` |  Nullable |
| `current_deadline` | `text` |  Nullable |
| `requested_deadline` | `text` |  Nullable |
| `reason` | `text` |  Nullable |
| `status` | `text` |  Nullable |
| `manager_note` | `text` |  Nullable |
| `manager_deadline` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `company_sops`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `department` | `text` |  Nullable |
| `task_type` | `text` |  Nullable |
| `content` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `boss_reviews`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `review_id` | `uuid` | Primary |
| `employee_name` | `text` |  |
| `review_date` | `text` |  Nullable |
| `performance_summary` | `text` |  Nullable |
| `rating` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `employees`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `name` | `text` |  Unique |
| `department` | `text` |  |
| `phone_number` | `text` |  Nullable |
| `email` | `text` |  Nullable |
| `created_at` | `timestamptz` |  |
| `employee_number` | `int8` |  Nullable Unique |

## Table `task_history`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `task_id` | `text` |  |
| `edited_by` | `text` |  |
| `edited_at` | `timestamptz` |  |
| `changes` | `jsonb` |  Nullable |
| `old_task` | `jsonb` |  Nullable |
| `new_task` | `jsonb` |  Nullable |

## Table `workflows`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `workflow_id` | `text` |  Unique |
| `name` | `text` |  |
| `instruction` | `text` |  |
| `status` | `text` |  |
| `created_by` | `text` |  |
| `start_date` | `timestamptz` |  |
| `target_completion` | `timestamptz` |  |
| `actual_completion` | `timestamptz` |  Nullable |
| `created_at` | `timestamptz` |  |

## Table `task_dependencies`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `workflow_id` | `uuid` |  |
| `predecessor_task_id` | `text` |  |
| `successor_task_id` | `text` |  |
| `dependency_type` | `text` |  |
| `is_satisfied` | `bool` |  |
| `satisfied_at` | `timestamptz` |  Nullable |

## Table `workflow_participants`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `workflow_id` | `uuid` |  |
| `employee_id` | `uuid` |  Nullable |
| `employee_name` | `text` |  |
| `employee_number` | `int8` |  Nullable |
| `department` | `text` |  |
| `stage_number` | `int4` |  |
| `role` | `text` |  |
| `joined_at` | `timestamptz` |  |

## Table `task_nudges`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `workflow_id` | `uuid` |  |
| `task_id` | `text` |  |
| `sender_name` | `text` |  |
| `receiver_name` | `text` |  |
| `message` | `text` |  |
| `created_at` | `timestamptz` |  |

## Table `task_handover_events`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `workflow_id` | `uuid` |  |
| `from_task_id` | `text` |  |
| `to_task_id` | `text` |  |
| `from_employee` | `text` |  |
| `to_employee` | `text` |  |
| `notes` | `text` |  Nullable |
| `created_at` | `timestamptz` |  |

## Table `task_delay_events`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `workflow_id` | `uuid` |  |
| `task_id` | `text` |  |
| `reported_by` | `text` |  |
| `reason` | `text` |  |
| `created_at` | `timestamptz` |  |

## RLS Policies

### `purchase_orders`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow insert access to all` | INSERT | public | PERMISSIVE | — | `true` |
| `Allow read access to all` | SELECT | public | PERMISSIVE | `true` | — |

### `inventory`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow full access to inventory` | ALL | public | PERMISSIVE | `true` | `true` |

### `part_vendors`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow anonymous insert access` | INSERT | public | PERMISSIVE | — | `true` |
| `Allow anonymous read access` | SELECT | public | PERMISSIVE | `true` | — |
| `Allow anonymous update access` | UPDATE | public | PERMISSIVE | `true` | — |

### `monthly_goals`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow public insert` | INSERT | public | PERMISSIVE | — | `true` |
| `Allow public select` | SELECT | public | PERMISSIVE | `true` | — |
| `Allow public update` | UPDATE | public | PERMISSIVE | `true` | — |

### `extension_requests`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow public insert` | INSERT | public | PERMISSIVE | — | `true` |
| `Allow public select` | SELECT | public | PERMISSIVE | `true` | — |
| `Allow public update` | UPDATE | public | PERMISSIVE | `true` | — |

### `boss_reviews`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow read access on boss_reviews` | SELECT | public | PERMISSIVE | `true` | — |

### `employees`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow full access on employees` | ALL | public | PERMISSIVE | `true` | — |
| `Allow read access on employees` | SELECT | public | PERMISSIVE | `true` | — |

### `task_history`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow insert access on task_history` | INSERT | public | PERMISSIVE | — | `true` |
| `Allow read access on task_history` | SELECT | public | PERMISSIVE | `true` | — |

### `tasks`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `Allow public insert` | INSERT | public | PERMISSIVE | — | `true` |
| `Allow public select` | SELECT | public | PERMISSIVE | `true` | — |
| `Allow public update` | UPDATE | public | PERMISSIVE | `true` | — |

