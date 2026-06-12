def normalize_user_full_name(doc, method=None):
	if doc.full_name:
		doc.full_name = " ".join(doc.full_name.split())
