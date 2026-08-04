# Drafts

Drafts represent records that may not yet be inserted. Primary keyed tables all generate a draft by default where the draft's primary key is optional, allowing the database to initialize this value.

## Form features work with drafts

Drafts unify features that want to _create_ a record and features that want to _edit_ a record:

```swift
struct FormView: View {
  @State var draft: Reminder.Draft
  @Dependency(\.defaultDatabase) var database
  var body: some View {
    ...
  }

  func saveButtonTapped() {
    try database.write { db in
      try Reminder.upsert { draft }.execute(db)
    }
  }
}
```

## Upsert to save a draft

```swift
try await database.write { db in
  try Reminder.upsert { draft }.execute(db)
}
```

## Drafts are not `Identifiable` by default

Optional `id` makes `Identifiable` conformance for `Draft` dangerous. Multiple unrelated drafts can have same "identity" if their `id` is `nil`.

## Lazy initializable columns

Use `@Column(lazyInitializable: true)` to optionalize a draft's column.

```swift
@Table struct Reminder: Identifiable {
  let id: UUID
  var name = ""
  @Column(lazyInitializable: true)
  var remindersListID: RemindersList.ID
  @Column(lazyInitializable: true)
  var createdAt: Date
  @Column(lazyInitializable: true)
  var updatedAt: Date
}
```

The generated draft optionalizes each column so they are not necessary to instantiate:

```swift
var reminderDraft = Reminder()
```

> Note: `id` is automatically lazy-initializable because it's a primary key.

Enable the `LazyInitializableByDefault` package trait to automatically optionalize columns with no
default. With the trait turned on, each explicit `@Column(lazyInitializable: true)` can be omitted
because there is no default value in Swift:

```swift
@Table struct Reminder: Identifiable {
  let id: UUID
  var name = ""
  var remindersListID: RemindersList.ID
  var createdAt: Date
  var updatedAt: Date
}
```
