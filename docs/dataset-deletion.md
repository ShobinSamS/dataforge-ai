# Delete unneeded datasets

In **Dataset gallery**, choose the dataset from the selector, click **Delete
dataset**, then check the name and short version ID in the confirmation dialog.
Confirming permanently removes that generation job, its generated samples,
annotations, masks, quality records and local export archives. The input template,
other datasets, and previously downloaded copies are kept. The text dataset
viewer provides the same action for text records and their local exports.

Cancel queued/running generation first, and wait for its status to stop before
deleting. Active and cancelling jobs cannot be deleted. Failed, paused, cancelled,
completed and review-required jobs can be deleted; deletion also removes Resume.

The API exposes `DELETE /api/jobs/{id}` and `DELETE /api/text/jobs/{id}`. It deletes
the dependent export/sample metadata and the job in one database transaction.
Cleanup only targets canonical folders owned by the selected job and canonical
export files; stored arbitrary paths, symlinks/junctions escaping storage, and
source templates are not followed or deleted. Cleanup warnings are returned to
the UI if local files are locked or noncanonical. No automatic dataset deletion
is performed during app startup or upgrade.
