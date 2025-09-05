frappe.ui.form.on('ENJO Aktionseinstellungen', {
	onload(frm) {
		update_period_editor_options(frm);
		add_active_period_indicators(frm);
		update_dynamic_visibility(frm);
		update_variant_count_indicators(frm);
		update_schwellwerte_labels(frm);
	},
	refresh(frm) {
		update_period_editor_options(frm);
		add_active_period_indicators(frm);
		update_dynamic_visibility(frm);
		update_variant_count_indicators(frm);
		update_schwellwerte_labels(frm);
	},
	period_1_label(frm) {
		update_period_editor_options(frm);
		add_active_period_indicators(frm);
		update_schwellwerte_labels(frm);
	},
	period_2_label(frm) {
		update_period_editor_options(frm);
		add_active_period_indicators(frm);
		update_schwellwerte_labels(frm);
	},
	period_editor(frm) {
		update_period_editor_options(frm);
		update_dynamic_visibility(frm);
		update_variant_count_indicators(frm);
		update_schwellwerte_labels(frm);
	},
	period_1_from(frm) {
		add_active_period_indicators(frm);
		const label1 = frm.doc.period_1_label || 'Aktion 1';
		const label2 = frm.doc.period_2_label || 'Aktion 2';
		update_section_labels(frm, label1, label2);
	},
	period_1_to(frm) {
		add_active_period_indicators(frm);
		const label1 = frm.doc.period_1_label || 'Aktion 1';
		const label2 = frm.doc.period_2_label || 'Aktion 2';
		update_section_labels(frm, label1, label2);
	},
	period_2_from(frm) {
		add_active_period_indicators(frm);
		const label1 = frm.doc.period_1_label || 'Aktion 1';
		const label2 = frm.doc.period_2_label || 'Aktion 2';
		update_section_labels(frm, label1, label2);
	},
	period_2_to(frm) {
		add_active_period_indicators(frm);
		const label1 = frm.doc.period_1_label || 'Aktion 1';
		const label2 = frm.doc.period_2_label || 'Aktion 2';
		update_section_labels(frm, label1, label2);
	}
});

// Event Handlers für dynamische Sichtbarkeit
// Standard Varianten (Aktion 1) - sowohl Name als auch Code Felder
frappe.ui.form.on('ENJO Aktionseinstellungen', {
		s1_1_name(frm) {
		console.log('🎯 S1.1 Name geändert:', frm.doc.s1_1_name);
		update_dynamic_visibility(frm);
		update_variant_count_indicators(frm);
		// Keine direkten toggle_display Aufrufe um Zuklappen zu vermeiden
	},
	s1_1_code(frm) { 
		console.log('🎯 S1.1 Code geändert:', frm.doc.s1_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// Keine direkten toggle_display Aufrufe um Zuklappen zu vermeiden
	},
	s2_1_name(frm) { 
		console.log('🎯 S2.1 Name geändert:', frm.doc.s2_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// Keine direkten toggle_display Aufrufe um Zuklappen zu vermeiden
	},
	s2_1_code(frm) { 
		console.log('🎯 S2.1 Code geändert:', frm.doc.s2_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// Keine direkten toggle_display Aufrufe um Zuklappen zu vermeiden
	},
	s3_1_name(frm) { 
		console.log('🎯 S3.1 Name geändert:', frm.doc.s3_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige S4 an wenn S3 ausgefüllt
		if (frm.doc.s3_1_name && frm.doc.s3_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige S4 an weil S3.1 Name ausgefüllt');
			frm.toggle_display('section_break_s4', true);
			frm.toggle_display('s4_1_name', true);
			frm.toggle_display('s4_1_code', true);
			frm.toggle_display('column_break_s4', true);
		}
	},
	s3_1_code(frm) { 
		console.log('🎯 S3.1 Code geändert:', frm.doc.s3_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige S4 an wenn S3 ausgefüllt
		if (frm.doc.s3_1_code && frm.doc.s3_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige S4 an weil S3.1 Code ausgefüllt');
			frm.toggle_display('section_break_s4', true);
			frm.toggle_display('s4_1_name', true);
			frm.toggle_display('s4_1_code', true);
			frm.toggle_display('column_break_s4', true);
		}
	},
	s4_1_name(frm) { 
		console.log('🎯 S4.1 Name geändert:', frm.doc.s4_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige S5 an wenn S4 ausgefüllt
		if (frm.doc.s4_1_name && frm.doc.s4_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige S5 an weil S4.1 Name ausgefüllt');
			frm.toggle_display('section_break_s5', true);
			frm.toggle_display('s5_1_name', true);
			frm.toggle_display('s5_1_code', true);
			frm.toggle_display('column_break_s5', true);
		}
	},
	s4_1_code(frm) { 
		console.log('🎯 S4.1 Code geändert:', frm.doc.s4_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige S5 an wenn S4 ausgefüllt
		if (frm.doc.s4_1_code && frm.doc.s4_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige S5 an weil S4.1 Code ausgefüllt');
			frm.toggle_display('section_break_s5', true);
			frm.toggle_display('s5_1_name', true);
			frm.toggle_display('s5_1_code', true);
			frm.toggle_display('column_break_s5', true);
		}
	},
	s5_1_name(frm) { 
		console.log('🎯 S5.1 Name geändert:', frm.doc.s5_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	},
	s5_1_code(frm) { 
		console.log('🎯 S5.1 Code geändert:', frm.doc.s5_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	},
	// Premium Varianten (Aktion 1)
	p1_1_name(frm) { 
		console.log('🎯 P1.1 Name geändert:', frm.doc.p1_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P2 an wenn P1 ausgefüllt
		if (frm.doc.p1_1_name && frm.doc.p1_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige P2 an weil P1.1 Name ausgefüllt');
			frm.toggle_display('section_break_p2', true);
			frm.toggle_display('p2_1_name', true);
			frm.toggle_display('p2_1_code', true);
			frm.toggle_display('column_break_p2', true);
		}
	},
	p1_1_code(frm) { 
		console.log('🎯 P1.1 Code geändert:', frm.doc.p1_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P2 an wenn P1 ausgefüllt
		if (frm.doc.p1_1_code && frm.doc.p1_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige P2 an weil P1.1 Code ausgefüllt');
			frm.toggle_display('section_break_p2', true);
			frm.toggle_display('p2_1_name', true);
			frm.toggle_display('p2_1_code', true);
			frm.toggle_display('column_break_p2', true);
		}
	},
	p2_1_name(frm) { 
		console.log('🎯 P2.1 Name geändert:', frm.doc.p2_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P3 an wenn P2 ausgefüllt
		if (frm.doc.p2_1_name && frm.doc.p2_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige P3 an weil P2.1 Name ausgefüllt');
			frm.toggle_display('section_break_p3', true);
			frm.toggle_display('p3_1_name', true);
			frm.toggle_display('p3_1_code', true);
			frm.toggle_display('column_break_p3', true);
		}
	},
	p2_1_code(frm) { 
		console.log('🎯 P2.1 Code geändert:', frm.doc.p2_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P3 an wenn P2 ausgefüllt
		if (frm.doc.p2_1_code && frm.doc.p2_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige P3 an weil P2.1 Code ausgefüllt');
			frm.toggle_display('section_break_p3', true);
			frm.toggle_display('p3_1_name', true);
			frm.toggle_display('p3_1_code', true);
			frm.toggle_display('column_break_p3', true);
		}
	},
	p3_1_name(frm) { 
		console.log('🎯 P3.1 Name geändert:', frm.doc.p3_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P4 an wenn P3 ausgefüllt
		if (frm.doc.p3_1_name && frm.doc.p3_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige P4 an weil P3.1 Name ausgefüllt');
			frm.toggle_display('section_break_p4', true);
			frm.toggle_display('p4_1_name', true);
			frm.toggle_display('p4_1_code', true);
			frm.toggle_display('column_break_p4', true);
		}
	},
	p3_1_code(frm) { 
		console.log('🎯 P3.1 Code geändert:', frm.doc.p3_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P4 an wenn P3 ausgefüllt
		if (frm.doc.p3_1_code && frm.doc.p3_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige P4 an weil P3.1 Code ausgefüllt');
			frm.toggle_display('section_break_p4', true);
			frm.toggle_display('p4_1_name', true);
			frm.toggle_display('p4_1_code', true);
			frm.toggle_display('column_break_p4', true);
		}
	},
	p4_1_name(frm) { 
		console.log('🎯 P4.1 Name geändert:', frm.doc.p4_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P5 an wenn P4 ausgefüllt
		if (frm.doc.p4_1_name && frm.doc.p4_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige P5 an weil P4.1 Name ausgefüllt');
			frm.toggle_display('section_break_p5', true);
			frm.toggle_display('p5_1_name', true);
			frm.toggle_display('p5_1_code', true);
			frm.toggle_display('column_break_p5', true);
		}
	},
	p4_1_code(frm) { 
		console.log('🎯 P4.1 Code geändert:', frm.doc.p4_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige P5 an wenn P4 ausgefüllt
		if (frm.doc.p4_1_code && frm.doc.p4_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige P5 an weil P4.1 Code ausgefüllt');
			frm.toggle_display('section_break_p5', true);
			frm.toggle_display('p5_1_name', true);
			frm.toggle_display('p5_1_code', true);
			frm.toggle_display('column_break_p5', true);
		}
	},
	p5_1_name(frm) { 
		console.log('🎯 P5.1 Name geändert:', frm.doc.p5_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	},
	p5_1_code(frm) { 
		console.log('🎯 P5.1 Code geändert:', frm.doc.p5_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	},
	// Standard Varianten (Aktion 2)
	z2_s1_1_name(frm) { 
		console.log('🎯 Z2_S1.1 Name geändert:', frm.doc.z2_s1_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S2 an wenn Z2_S1 ausgefüllt
		if (frm.doc.z2_s1_1_name && frm.doc.z2_s1_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S2 an weil Z2_S1.1 Name ausgefüllt');
			frm.toggle_display('section_break_s2_z2', true);
			frm.toggle_display('z2_s2_1_name', true);
			frm.toggle_display('z2_s2_1_code', true);
			frm.toggle_display('column_break_s2_z2', true);
		}
	},
	z2_s1_1_code(frm) { 
		console.log('🎯 Z2_S1.1 Code geändert:', frm.doc.z2_s1_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S2 an wenn Z2_S1 ausgefüllt
		if (frm.doc.z2_s1_1_code && frm.doc.z2_s1_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S2 an weil Z2_S1.1 Code ausgefüllt');
			frm.toggle_display('section_break_s2_z2', true);
			frm.toggle_display('z2_s2_1_name', true);
			frm.toggle_display('z2_s2_1_code', true);
			frm.toggle_display('column_break_s2_z2', true);
		}
	},
	z2_s2_1_name(frm) { 
		console.log('🎯 Z2_S2.1 Name geändert:', frm.doc.z2_s2_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S3 an wenn Z2_S2 ausgefüllt
		if (frm.doc.z2_s2_1_name && frm.doc.z2_s2_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S3 an weil Z2_S2.1 Name ausgefüllt');
			frm.toggle_display('section_break_s3_z2', true);
			frm.toggle_display('z2_s3_1_name', true);
			frm.toggle_display('z2_s3_1_code', true);
			frm.toggle_display('column_break_s3_z2', true);
		}
	},
	z2_s2_1_code(frm) { 
		console.log('🎯 Z2_S2.1 Code geändert:', frm.doc.z2_s2_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S3 an wenn Z2_S2 ausgefüllt
		if (frm.doc.z2_s2_1_code && frm.doc.z2_s2_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S3 an weil Z2_S2.1 Code ausgefüllt');
			frm.toggle_display('section_break_s3_z2', true);
			frm.toggle_display('z2_s3_1_name', true);
			frm.toggle_display('z2_s3_1_code', true);
			frm.toggle_display('column_break_s3_z2', true);
		}
	},
	z2_s3_1_name(frm) { 
		console.log('🎯 Z2_S3.1 Name geändert:', frm.doc.z2_s3_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S4 an wenn Z2_S3 ausgefüllt
		if (frm.doc.z2_s3_1_name && frm.doc.z2_s3_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S4 an weil Z2_S3.1 Name ausgefüllt');
			frm.toggle_display('section_break_s4_z2', true);
			frm.toggle_display('z2_s4_1_name', true);
			frm.toggle_display('z2_s4_1_code', true);
			frm.toggle_display('column_break_s4_z2', true);
		}
	},
	z2_s3_1_code(frm) { 
		console.log('🎯 Z2_S3.1 Code geändert:', frm.doc.z2_s3_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S4 an wenn Z2_S3 ausgefüllt
		if (frm.doc.z2_s3_1_code && frm.doc.z2_s3_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S4 an weil Z2_S3.1 Code ausgefüllt');
			frm.toggle_display('section_break_s4_z2', true);
			frm.toggle_display('z2_s4_1_name', true);
			frm.toggle_display('z2_s4_1_code', true);
			frm.toggle_display('column_break_s4_z2', true);
		}
	},
	z2_s4_1_name(frm) { 
		console.log('🎯 Z2_S4.1 Name geändert:', frm.doc.z2_s4_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S5 an wenn Z2_S4 ausgefüllt
		if (frm.doc.z2_s4_1_name && frm.doc.z2_s4_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S5 an weil Z2_S4.1 Name ausgefüllt');
			frm.toggle_display('section_break_s5_z2', true);
			frm.toggle_display('z2_s5_1_name', true);
			frm.toggle_display('z2_s5_1_code', true);
			frm.toggle_display('column_break_s5_z2', true);
		}
	},
	z2_s4_1_code(frm) { 
		console.log('🎯 Z2_S4.1 Code geändert:', frm.doc.z2_s4_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_S5 an wenn Z2_S4 ausgefüllt
		if (frm.doc.z2_s4_1_code && frm.doc.z2_s4_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_S5 an weil Z2_S4.1 Code ausgefüllt');
			frm.toggle_display('section_break_s5_z2', true);
			frm.toggle_display('z2_s5_1_name', true);
			frm.toggle_display('z2_s5_1_code', true);
			frm.toggle_display('column_break_s5_z2', true);
		}
	},
	z2_s5_1_name(frm) { 
		console.log('🎯 Z2_S5.1 Name geändert:', frm.doc.z2_s5_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	},
	z2_s5_1_code(frm) { 
		console.log('🎯 Z2_S5.1 Code geändert:', frm.doc.z2_s5_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	},
	// Premium Varianten (Aktion 2)
	z2_p1_1_name(frm) { 
		console.log('🎯 Z2_P1.1 Name geändert:', frm.doc.z2_p1_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P2 an wenn Z2_P1 ausgefüllt
		if (frm.doc.z2_p1_1_name && frm.doc.z2_p1_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P2 an weil Z2_P1.1 Name ausgefüllt');
			frm.toggle_display('section_break_p2_z2', true);
			frm.toggle_display('z2_p2_1_name', true);
			frm.toggle_display('z2_p2_1_code', true);
			frm.toggle_display('column_break_p2_z2', true);
		}
	},
	z2_p1_1_code(frm) { 
		console.log('🎯 Z2_P1.1 Code geändert:', frm.doc.z2_p1_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P2 an wenn Z2_P1 ausgefüllt
		if (frm.doc.z2_p1_1_code && frm.doc.z2_p1_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P2 an weil Z2_P1.1 Code ausgefüllt');
			frm.toggle_display('section_break_p2_z2', true);
			frm.toggle_display('z2_p2_1_name', true);
			frm.toggle_display('z2_p2_1_code', true);
			frm.toggle_display('column_break_p2_z2', true);
		}
	},
	z2_p2_1_name(frm) { 
		console.log('🎯 Z2_P2.1 Name geändert:', frm.doc.z2_p2_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P3 an wenn Z2_P2 ausgefüllt
		if (frm.doc.z2_p2_1_name && frm.doc.z2_p2_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P3 an weil Z2_P2.1 Name ausgefüllt');
			frm.toggle_display('section_break_p3_z2', true);
			frm.toggle_display('z2_p3_1_name', true);
			frm.toggle_display('z2_p3_1_code', true);
			frm.toggle_display('column_break_p3_z2', true);
		}
	},
	z2_p2_1_code(frm) { 
		console.log('🎯 Z2_P2.1 Code geändert:', frm.doc.z2_p2_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P3 an wenn Z2_P2 ausgefüllt
		if (frm.doc.z2_p2_1_code && frm.doc.z2_p2_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P3 an weil Z2_P2.1 Code ausgefüllt');
			frm.toggle_display('section_break_p3_z2', true);
			frm.toggle_display('z2_p3_1_name', true);
			frm.toggle_display('z2_p3_1_code', true);
			frm.toggle_display('column_break_p3_z2', true);
		}
	},
	z2_p3_1_name(frm) { 
		console.log('🎯 Z2_P3.1 Name geändert:', frm.doc.z2_p3_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P4 an wenn Z2_P3 ausgefüllt
		if (frm.doc.z2_p3_1_name && frm.doc.z2_p3_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P4 an weil Z2_P3.1 Name ausgefüllt');
			frm.toggle_display('section_break_p4_z2', true);
			frm.toggle_display('z2_p4_1_name', true);
			frm.toggle_display('z2_p4_1_code', true);
			frm.toggle_display('column_break_p4_z2', true);
		}
	},
	z2_p3_1_code(frm) { 
		console.log('🎯 Z2_P3.1 Code geändert:', frm.doc.z2_p3_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P4 an wenn Z2_P3 ausgefüllt
		if (frm.doc.z2_p3_1_code && frm.doc.z2_p3_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P4 an weil Z2_P3.1 Code ausgefüllt');
			frm.toggle_display('section_break_p4_z2', true);
			frm.toggle_display('z2_p4_1_name', true);
			frm.toggle_display('z2_p4_1_code', true);
			frm.toggle_display('column_break_p4_z2', true);
		}
	},
	z2_p4_1_name(frm) { 
		console.log('🎯 Z2_P4.1 Name geändert:', frm.doc.z2_p4_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P5 an wenn Z2_P4 ausgefüllt
		if (frm.doc.z2_p4_1_name && frm.doc.z2_p4_1_name.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P5 an weil Z2_P4.1 Name ausgefüllt');
			frm.toggle_display('section_break_p5_z2', true);
			frm.toggle_display('z2_p5_1_name', true);
			frm.toggle_display('z2_p5_1_code', true);
			frm.toggle_display('column_break_p5_z2', true);
		}
	},
	z2_p4_1_code(frm) { 
		console.log('🎯 Z2_P4.1 Code geändert:', frm.doc.z2_p4_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
		// SOFORTIGE REAKTION: Zeige Z2_P5 an wenn Z2_P4 ausgefüllt
		if (frm.doc.z2_p4_1_code && frm.doc.z2_p4_1_code.trim()) {
			console.log('🎯 SOFORT: Zeige Z2_P5 an weil Z2_P4.1 Code ausgefüllt');
			frm.toggle_display('section_break_p5_z2', true);
			frm.toggle_display('z2_p5_1_name', true);
			frm.toggle_display('z2_p5_1_code', true);
			frm.toggle_display('column_break_p5_z2', true);
		}
	},
	z2_p5_1_name(frm) { 
		console.log('🎯 Z2_P5.1 Name geändert:', frm.doc.z2_p5_1_name);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	},
	z2_p5_1_code(frm) { 
		console.log('🎯 Z2_P5.1 Code geändert:', frm.doc.z2_p5_1_code);
		update_dynamic_visibility(frm); 
		update_variant_count_indicators(frm);
	}
});

// Event Handlers für progressive Varianten-Anzeige (alle .2-.6 Felder)
frappe.ui.form.on('ENJO Aktionseinstellungen', {
	// Standard Aktion 1
	s1_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s1_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s1_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s1_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s1_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s1_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s1_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s1_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s2_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s2_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s2_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s2_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s2_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s2_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s2_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s2_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s3_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s3_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s3_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s3_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s3_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s3_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s3_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s3_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s4_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s4_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s4_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s4_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s4_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s4_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s4_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s4_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s5_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s5_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s5_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s5_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s5_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s5_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s5_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s5_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s1_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s1_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s2_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s2_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s3_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s3_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s4_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s4_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	s5_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, s5_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	// Premium Aktion 1
	p1_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p1_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p1_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p1_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p1_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p1_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p1_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p1_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p2_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p2_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p2_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p2_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p2_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p2_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p2_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p2_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p3_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p3_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p3_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p3_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p3_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p3_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p3_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p3_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p4_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p4_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p4_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p4_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p4_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p4_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p4_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p4_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p5_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p5_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p5_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p5_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p5_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p5_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p5_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p5_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p1_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p1_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p2_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p2_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p3_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p3_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p4_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p4_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	p5_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, p5_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	// Standard Aktion 2
	z2_s1_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s1_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s1_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s1_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s1_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s1_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s1_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s1_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s2_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s2_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s2_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s2_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s2_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s2_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s2_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s2_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s3_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s3_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s3_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s3_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s3_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s3_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s3_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s3_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s4_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s4_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s4_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s4_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s4_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s4_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s4_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s4_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s5_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s5_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s5_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s5_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s5_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s5_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s5_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s5_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s1_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s1_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s2_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s2_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s3_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s3_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s4_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s4_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_s5_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_s5_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	// Premium Aktion 2
	z2_p1_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p1_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p1_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p1_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p1_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p1_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p1_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p1_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p2_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p2_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p2_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p2_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p2_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p2_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p2_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p2_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p3_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p3_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p3_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p3_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p3_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p3_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p3_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p3_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p4_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p4_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p4_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p4_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p4_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p4_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p4_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p4_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p5_2_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p5_2_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p5_3_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p5_3_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p5_4_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p5_4_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p5_5_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p5_5_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p1_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p1_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p2_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p2_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p3_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p3_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p4_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p4_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); },
	z2_p5_6_name(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }, z2_p5_6_code(frm) { update_dynamic_visibility(frm); update_variant_count_indicators(frm); }
});

// Labels werden jetzt statisch in der JSON definiert

function update_period_editor_options(frm) {
	const label1 = frm.doc.period_1_label || 'Aktion 1';
	const label2 = frm.doc.period_2_label || 'Aktion 2';

	// Update Dropdown Options
	frm.set_df_property('period_editor', 'options', [
		{ label: label1, value: '1' },
		{ label: label2, value: '2' }
	]);

	if (frm.doc.period_editor !== '1' && frm.doc.period_editor !== '2') {
		frm.set_value('period_editor', '1');
	}
	frm.refresh_field('period_editor');

	// Update Section Break Labels dynamisch
	update_section_labels(frm, label1, label2);
}

function update_section_labels(frm, label1, label2) {
	console.log('=== DEBUG: update_section_labels ===');
	console.log('Label1:', label1);
	console.log('Label2:', label2);
	
	// HTML Header für Aktion 1 & 2 (mit aktuellem Indikator)
	const today = frappe.datetime.nowdate();
	const period1Active = isActivePeriod(frm.doc.period_1_from, frm.doc.period_1_to, today);
	const period2Active = isActivePeriod(frm.doc.period_2_from, frm.doc.period_2_to, today);
	
	console.log('Period 1 active:', period1Active);
	console.log('Period 2 active:', period2Active);
	
	const activeIndicator1 = period1Active ? ' <span style="color: #28a745; font-weight: bold;">AKTUELL</span>' : '';
	const activeIndicator2 = period2Active ? ' <span style="color: #28a745; font-weight: bold;">AKTUELL</span>' : '';
	
	console.log('Active indicator 1:', activeIndicator1);
	console.log('Active indicator 2:', activeIndicator2);
	
	// Standard Headers
	console.log('Setting html_action_1_header...');
	frm.set_df_property('html_action_1_header', 'options', 
		`<h3 style="color: #333; margin: 20px 0 10px 0; font-weight: bold;">Standard ${label1}${activeIndicator1}</h3>`
	);
	
	console.log('Setting html_action_2_header...');
	frm.set_df_property('html_action_2_header', 'options', 
		`<h3 style="color: #333; margin: 20px 0 10px 0; font-weight: bold;">Standard ${label2}${activeIndicator2}</h3>`
	);
	
	// Premium Headers
	console.log('Setting html_action_1_premium_header...');
	frm.set_df_property('html_action_1_premium_header', 'options', 
		`<h3 style="color: #333; margin: 20px 0 10px 0; font-weight: bold;">Premium ${label1}${activeIndicator1}</h3>`
	);
	
	console.log('Setting html_action_2_premium_header...');
	frm.set_df_property('html_action_2_premium_header', 'options', 
		`<h3 style="color: #333; margin: 20px 0 10px 0; font-weight: bold;">Premium ${label2}${activeIndicator2}</h3>`
	);
	
	console.log('=== END DEBUG ===');
}

function isActivePeriod(from_date, to_date, today) {
	if (!from_date || !to_date) return false;
	return frappe.datetime.get_diff(to_date, today) >= 0 && 
	       frappe.datetime.get_diff(today, from_date) >= 0;
}

function add_active_period_indicators(frm) {
	// Prüfe welche Periode aktuell aktiv ist
	const today = frappe.datetime.nowdate();
	
	function isActivePeriod(from_date, to_date) {
		if (!from_date || !to_date) return false;
		return frappe.datetime.get_diff(to_date, today) >= 0 && 
		       frappe.datetime.get_diff(today, from_date) >= 0;
	}
	
	const period1Active = isActivePeriod(frm.doc.period_1_from, frm.doc.period_1_to);
	const period2Active = isActivePeriod(frm.doc.period_2_from, frm.doc.period_2_to);
	
	// Aktualisiere die Bezeichnungsfelder mit grünen Indikatoren
	setTimeout(() => {
		// Aktion 1 Indikator
		const label1Field = frm.fields_dict.period_1_label;
		if (label1Field && label1Field.$wrapper) {
			const labelWrapper = label1Field.$wrapper.find('.control-label');
			if (labelWrapper.length) {
				let indicator = '';
				if (period1Active) {
					indicator = '   <span style="color: #28a745; font-weight: bold;">AKTUELL</span>';
				}
				labelWrapper.html(`Bezeichnung Aktion 1${indicator}`);
			}
		}
		
		// Aktion 2 Indikator  
		const label2Field = frm.fields_dict.period_2_label;
		if (label2Field && label2Field.$wrapper) {
			const labelWrapper = label2Field.$wrapper.find('.control-label');
			if (labelWrapper.length) {
				let indicator = '';
				if (period2Active) {
					indicator = '   <span style="color: #28a745; font-weight: bold;">AKTUELL</span>';
				}
				labelWrapper.html(`Bezeichnung Aktion 2${indicator}`);
			}
		}
		
		// Aktualisiere auch die Zeitraum-Labels
		updatePeriodLabels(frm, period1Active, period2Active);
	}, 100);
}

function updatePeriodLabels(frm, period1Active, period2Active) {
	// Zeitraum 1 Indikatoren
	const period1FromField = frm.fields_dict.period_1_from;
	if (period1FromField && period1FromField.$wrapper) {
		const labelWrapper = period1FromField.$wrapper.find('.control-label');
		if (labelWrapper.length) {
			if (period1Active) {
				labelWrapper.html('<span style="color: #28a745; font-weight: bold;">Zeitraum 1: Von</span>');
			} else {
				labelWrapper.html('Zeitraum 1: Von');
			}
		}
	}
	
	const period1ToField = frm.fields_dict.period_1_to;
	if (period1ToField && period1ToField.$wrapper) {
		const labelWrapper = period1ToField.$wrapper.find('.control-label');
		if (labelWrapper.length) {
			if (period1Active) {
				labelWrapper.html('<span style="color: #28a745; font-weight: bold;">Zeitraum 1: Bis</span>');
			} else {
				labelWrapper.html('Zeitraum 1: Bis');
			}
		}
	}
	
	// Zeitraum 2 Indikatoren
	const period2FromField = frm.fields_dict.period_2_from;
	if (period2FromField && period2FromField.$wrapper) {
		const labelWrapper = period2FromField.$wrapper.find('.control-label');
		if (labelWrapper.length) {
			if (period2Active) {
				labelWrapper.html('<span style="color: #28a745; font-weight: bold;">Zeitraum 2: Von</span>');
			} else {
				labelWrapper.html('Zeitraum 2: Von');
			}
		}
	}
	
	const period2ToField = frm.fields_dict.period_2_to;
	if (period2ToField && period2ToField.$wrapper) {
		const labelWrapper = period2ToField.$wrapper.find('.control-label');
		if (labelWrapper.length) {
			if (period2Active) {
				labelWrapper.html('<span style="color: #28a745; font-weight: bold;">Zeitraum 2: Bis</span>');
			} else {
				labelWrapper.html('Zeitraum 2: Bis');
			}
		}
	}
}

function update_dynamic_visibility(frm) {
	const current_period = frm.doc.period_editor;
	
	console.log('=== DEBUG: update_dynamic_visibility ===');
	console.log('Current period:', current_period);
	console.log('S1.1 Name:', frm.doc.s1_1_name);
	console.log('S1.1 Code:', frm.doc.s1_1_code);
	console.log('P1.1 Name:', frm.doc.p1_1_name);
	console.log('P1.1 Code:', frm.doc.p1_1_code);
	console.log('Z2_S1.1 Name:', frm.doc.z2_s1_1_name);
	console.log('Z2_S1.1 Code:', frm.doc.z2_s1_1_code);
	console.log('Z2_P1.1 Name:', frm.doc.z2_p1_1_name);
	console.log('Z2_P1.1 Code:', frm.doc.z2_p1_1_code);
	console.log('Period 1 label:', frm.doc.period_1_label);
	console.log('Period 2 label:', frm.doc.period_2_label);
	console.log('P1 fields exist check:');
	console.log('- section_break_p1_z2:', !!frm.fields_dict.section_break_p1_z2);
	console.log('- z2_p1_1_name:', !!frm.fields_dict.z2_p1_1_name);
	console.log('- z2_p1_1_code:', !!frm.fields_dict.z2_p1_1_code);
	
	// Alle Headers IMMER sichtbar machen (nur Inhalt ändert sich)
	console.log('Setting headers visibility by selected period...');
	const showPeriod1 = current_period === '1';
	const showPeriod2 = current_period === '2';
	frm.toggle_display('html_action_1_header', showPeriod1);
	frm.toggle_display('html_action_1_premium_header', showPeriod1);
	frm.toggle_display('html_action_2_header', showPeriod2);
	frm.toggle_display('html_action_2_premium_header', showPeriod2);
	
	// Debug: Prüfe ob Headers existieren
	console.log('Header 1 exists:', !!frm.fields_dict.html_action_1_header);
	console.log('Header 1 premium exists:', !!frm.fields_dict.html_action_1_premium_header);
	console.log('Header 2 exists:', !!frm.fields_dict.html_action_2_header);
	console.log('Header 2 premium exists:', !!frm.fields_dict.html_action_2_premium_header);
	
	if (current_period === '1') {
		// Aktion 1: S1 und P1 Hauptfelder IMMER sichtbar machen
		frm.toggle_display('section_break_s1', true);
		frm.toggle_display('s1_1_name', true);
		frm.toggle_display('s1_1_code', true);
		frm.toggle_display('section_break_p1', true);
		frm.toggle_display('p1_1_name', true);
		frm.toggle_display('p1_1_code', true);
		
		// Aktion 2: S1 und P1 Hauptfelder verstecken
		frm.toggle_display('section_break_s1_z2', false);
		frm.toggle_display('z2_s1_1_name', false);
		frm.toggle_display('z2_s1_1_code', false);
		frm.toggle_display('section_break_p1_z2', false);
		frm.toggle_display('z2_p1_1_name', false);
		frm.toggle_display('z2_p1_1_code', false);
		
		// Aktion 1 Logic - Haupt-Sections (S1 ist immer sichtbar, S2-S5 nach Regel)
		console.log('🚀🚀🚀 Rufe update_main_section_visibility_simple für Aktion 1 auf');
		update_main_section_visibility_simple(frm, 'standard', '');
		update_main_section_visibility_simple(frm, 'premium', '');
		
		// Hauptsection-Sichtbarkeit wird vollständig von update_main_section_visibility_simple gesteuert
		
		// Aktion 1 Logic - Varianten-Sections
		update_section_visibility_simple(frm, 'standard', '');
		update_section_visibility_simple(frm, 'premium', '');
		
		// S1 und P1 NACH allen anderen Funktionen nochmal explizit anzeigen
		frm.toggle_display('section_break_s1', true);
		frm.toggle_display('s1_1_name', true);
		frm.toggle_display('s1_1_code', true);
		// S1-Varianten nur anzeigen wenn S1 ausgefüllt ist
		const s1_filled = (frm.doc.s1_1_name && frm.doc.s1_1_name.trim()) || (frm.doc.s1_1_code && frm.doc.s1_1_code.trim());
		frm.toggle_display('sb_s1_variants', s1_filled);
		
		frm.toggle_display('section_break_p1', true);
		frm.toggle_display('p1_1_name', true);
		frm.toggle_display('p1_1_code', true);
		// P1-Varianten nur anzeigen wenn P1 ausgefüllt ist
		const p1_filled = (frm.doc.p1_1_name && frm.doc.p1_1_name.trim()) || (frm.doc.p1_1_code && frm.doc.p1_1_code.trim());
		frm.toggle_display('sb_p1_variants', p1_filled);
		
		// SICHERHEITSÜBERPRÜFUNGEN: Hauptsections anzeigen basierend auf progressiver Logik
		const s2_filled = (frm.doc.s2_1_name && frm.doc.s2_1_name.trim()) || (frm.doc.s2_1_code && frm.doc.s2_1_code.trim());
		const s3_filled = (frm.doc.s3_1_name && frm.doc.s3_1_name.trim()) || (frm.doc.s3_1_code && frm.doc.s3_1_code.trim());
		const s4_filled = (frm.doc.s4_1_name && frm.doc.s4_1_name.trim()) || (frm.doc.s4_1_code && frm.doc.s4_1_code.trim());
		const s5_filled = (frm.doc.s5_1_name && frm.doc.s5_1_name.trim()) || (frm.doc.s5_1_code && frm.doc.s5_1_code.trim());
		
		const p2_filled = (frm.doc.p2_1_name && frm.doc.p2_1_name.trim()) || (frm.doc.p2_1_code && frm.doc.p2_1_code.trim());
		const p3_filled = (frm.doc.p3_1_name && frm.doc.p3_1_name.trim()) || (frm.doc.p3_1_code && frm.doc.p3_1_code.trim());
		const p4_filled = (frm.doc.p4_1_name && frm.doc.p4_1_name.trim()) || (frm.doc.p4_1_code && frm.doc.p4_1_code.trim());
		const p5_filled = (frm.doc.p5_1_name && frm.doc.p5_1_name.trim()) || (frm.doc.p5_1_code && frm.doc.p5_1_code.trim());
		
		// S2: Anzeigen wenn S1 ausgefüllt oder S2 ausgefüllt
		if (s1_filled || s2_filled) {
			frm.toggle_display('section_break_s2', true);
			frm.toggle_display('s2_1_name', true);
			frm.toggle_display('s2_1_code', true);
			frm.toggle_display('column_break_s2', true);
		}
		// S3: Anzeigen wenn S2 ausgefüllt oder S3 ausgefüllt
		if (s2_filled || s3_filled) {
			frm.toggle_display('section_break_s3', true);
			frm.toggle_display('s3_1_name', true);
			frm.toggle_display('s3_1_code', true);
			frm.toggle_display('column_break_s3', true);
		}
		// S4: Anzeigen wenn S3 ausgefüllt oder S4 ausgefüllt
		if (s3_filled || s4_filled) {
			frm.toggle_display('section_break_s4', true);
			frm.toggle_display('s4_1_name', true);
			frm.toggle_display('s4_1_code', true);
			frm.toggle_display('column_break_s4', true);
		}
		// S5: Anzeigen wenn S4 ausgefüllt oder S5 ausgefüllt
		if (s4_filled || s5_filled) {
			frm.toggle_display('section_break_s5', true);
			frm.toggle_display('s5_1_name', true);
			frm.toggle_display('s5_1_code', true);
			frm.toggle_display('column_break_s5', true);
		}
		
		// P2: Anzeigen wenn P1 ausgefüllt oder P2 ausgefüllt
		if (p1_filled || p2_filled) {
			frm.toggle_display('section_break_p2', true);
			frm.toggle_display('p2_1_name', true);
			frm.toggle_display('p2_1_code', true);
			frm.toggle_display('column_break_p2', true);
		}
		// P3: Anzeigen wenn P2 ausgefüllt oder P3 ausgefüllt
		if (p2_filled || p3_filled) {
			frm.toggle_display('section_break_p3', true);
			frm.toggle_display('p3_1_name', true);
			frm.toggle_display('p3_1_code', true);
			frm.toggle_display('column_break_p3', true);
		}
		// P4: Anzeigen wenn P3 ausgefüllt oder P4 ausgefüllt
		if (p3_filled || p4_filled) {
			frm.toggle_display('section_break_p4', true);
			frm.toggle_display('p4_1_name', true);
			frm.toggle_display('p4_1_code', true);
			frm.toggle_display('column_break_p4', true);
		}
		// P5: Anzeigen wenn P4 ausgefüllt oder P5 ausgefüllt
		if (p4_filled || p5_filled) {
			frm.toggle_display('section_break_p5', true);
			frm.toggle_display('p5_1_name', true);
			frm.toggle_display('p5_1_code', true);
			frm.toggle_display('column_break_p5', true);
		}
		
	} else if (current_period === '2') {
		// Aktion 2: S1 und P1 Hauptfelder IMMER sichtbar machen
		console.log('Setting Aktion 2 S1/P1 fields to visible...');
		frm.toggle_display('section_break_s1_z2', true);
		frm.toggle_display('z2_s1_1_name', true);
		frm.toggle_display('z2_s1_1_code', true);
		frm.toggle_display('section_break_p1_z2', true);
		frm.toggle_display('z2_p1_1_name', true);
		frm.toggle_display('z2_p1_1_code', true);
		console.log('Aktion 2 S1/P1 fields set to visible');
		
		// Aktion 1: S1 und P1 Hauptfelder verstecken
		frm.toggle_display('section_break_s1', false);
		frm.toggle_display('s1_1_name', false);
		frm.toggle_display('s1_1_code', false);
		frm.toggle_display('section_break_p1', false);
		frm.toggle_display('p1_1_name', false);
		frm.toggle_display('p1_1_code', false);
		
		// Aktion 2 Logic - Haupt-Sections
		console.log('🚀🚀🚀 Rufe update_main_section_visibility_simple für Aktion 2 auf');
		update_main_section_visibility_simple(frm, 'standard', 'z2_');
		update_main_section_visibility_simple(frm, 'premium', 'z2_');
		
		// Hauptsection-Sichtbarkeit wird vollständig von update_main_section_visibility_simple gesteuert
		
		// Aktion 2 Logic - Varianten-Sections
		update_section_visibility_simple(frm, 'standard', 'z2_');
		update_section_visibility_simple(frm, 'premium', 'z2_');
		
		// S1 und P1 NACH allen anderen Funktionen nochmal explizit anzeigen
		frm.toggle_display('section_break_s1_z2', true);
		frm.toggle_display('z2_s1_1_name', true);
		frm.toggle_display('z2_s1_1_code', true);
		// S1-Varianten nur anzeigen wenn S1 ausgefüllt ist (Aktion 2)
		const z2_s1_filled = (frm.doc.z2_s1_1_name && frm.doc.z2_s1_1_name.trim()) || (frm.doc.z2_s1_1_code && frm.doc.z2_s1_1_code.trim());
		frm.toggle_display('sb_s1_variants_z2', z2_s1_filled);
		
		frm.toggle_display('section_break_p1_z2', true);
		frm.toggle_display('z2_p1_1_name', true);
		frm.toggle_display('z2_p1_1_code', true);
		// P1-Varianten nur anzeigen wenn P1 ausgefüllt ist (Aktion 2)
		const z2_p1_filled = (frm.doc.z2_p1_1_name && frm.doc.z2_p1_1_name.trim()) || (frm.doc.z2_p1_1_code && frm.doc.z2_p1_1_code.trim());
		frm.toggle_display('sb_p1_variants_z2', z2_p1_filled);
		
		// SICHERHEITSÜBERPRÜFUNGEN: Hauptsections anzeigen basierend auf progressiver Logik (Aktion 2)
		const z2_s2_filled = (frm.doc.z2_s2_1_name && frm.doc.z2_s2_1_name.trim()) || (frm.doc.z2_s2_1_code && frm.doc.z2_s2_1_code.trim());
		const z2_s3_filled = (frm.doc.z2_s3_1_name && frm.doc.z2_s3_1_name.trim()) || (frm.doc.z2_s3_1_code && frm.doc.z2_s3_1_code.trim());
		const z2_s4_filled = (frm.doc.z2_s4_1_name && frm.doc.z2_s4_1_name.trim()) || (frm.doc.z2_s4_1_code && frm.doc.z2_s4_1_code.trim());
		const z2_s5_filled = (frm.doc.z2_s5_1_name && frm.doc.z2_s5_1_name.trim()) || (frm.doc.z2_s5_1_code && frm.doc.z2_s5_1_code.trim());
		
		const z2_p2_filled = (frm.doc.z2_p2_1_name && frm.doc.z2_p2_1_name.trim()) || (frm.doc.z2_p2_1_code && frm.doc.z2_p2_1_code.trim());
		const z2_p3_filled = (frm.doc.z2_p3_1_name && frm.doc.z2_p3_1_name.trim()) || (frm.doc.z2_p3_1_code && frm.doc.z2_p3_1_code.trim());
		const z2_p4_filled = (frm.doc.z2_p4_1_name && frm.doc.z2_p4_1_name.trim()) || (frm.doc.z2_p4_1_code && frm.doc.z2_p4_1_code.trim());
		const z2_p5_filled = (frm.doc.z2_p5_1_name && frm.doc.z2_p5_1_name.trim()) || (frm.doc.z2_p5_1_code && frm.doc.z2_p5_1_code.trim());
		
		// S2: Anzeigen wenn S1 ausgefüllt oder S2 ausgefüllt (Aktion 2)
		if (z2_s1_filled || z2_s2_filled) {
			frm.toggle_display('section_break_s2_z2', true);
			frm.toggle_display('z2_s2_1_name', true);
			frm.toggle_display('z2_s2_1_code', true);
			frm.toggle_display('column_break_s2_z2', true);
		}
		// S3: Anzeigen wenn S2 ausgefüllt oder S3 ausgefüllt (Aktion 2)
		if (z2_s2_filled || z2_s3_filled) {
			frm.toggle_display('section_break_s3_z2', true);
			frm.toggle_display('z2_s3_1_name', true);
			frm.toggle_display('z2_s3_1_code', true);
			frm.toggle_display('column_break_s3_z2', true);
		}
		// S4: Anzeigen wenn S3 ausgefüllt oder S4 ausgefüllt (Aktion 2)
		if (z2_s3_filled || z2_s4_filled) {
			frm.toggle_display('section_break_s4_z2', true);
			frm.toggle_display('z2_s4_1_name', true);
			frm.toggle_display('z2_s4_1_code', true);
			frm.toggle_display('column_break_s4_z2', true);
		}
		// S5: Anzeigen wenn S4 ausgefüllt oder S5 ausgefüllt (Aktion 2)
		if (z2_s4_filled || z2_s5_filled) {
			frm.toggle_display('section_break_s5_z2', true);
			frm.toggle_display('z2_s5_1_name', true);
			frm.toggle_display('z2_s5_1_code', true);
			frm.toggle_display('column_break_s5_z2', true);
		}
		
		// P2: Anzeigen wenn P1 ausgefüllt oder P2 ausgefüllt (Aktion 2)
		if (z2_p1_filled || z2_p2_filled) {
			frm.toggle_display('section_break_p2_z2', true);
			frm.toggle_display('z2_p2_1_name', true);
			frm.toggle_display('z2_p2_1_code', true);
			frm.toggle_display('column_break_p2_z2', true);
		}
		// P3: Anzeigen wenn P2 ausgefüllt oder P3 ausgefüllt (Aktion 2)
		if (z2_p2_filled || z2_p3_filled) {
			frm.toggle_display('section_break_p3_z2', true);
			frm.toggle_display('z2_p3_1_name', true);
			frm.toggle_display('z2_p3_1_code', true);
			frm.toggle_display('column_break_p3_z2', true);
		}
		// P4: Anzeigen wenn P3 ausgefüllt oder P4 ausgefüllt (Aktion 2)
		if (z2_p3_filled || z2_p4_filled) {
			frm.toggle_display('section_break_p4_z2', true);
			frm.toggle_display('z2_p4_1_name', true);
			frm.toggle_display('z2_p4_1_code', true);
			frm.toggle_display('column_break_p4_z2', true);
		}
		// P5: Anzeigen wenn P4 ausgefüllt oder P5 ausgefüllt (Aktion 2)
		if (z2_p4_filled || z2_p5_filled) {
			frm.toggle_display('section_break_p5_z2', true);
			frm.toggle_display('z2_p5_1_name', true);
			frm.toggle_display('z2_p5_1_code', true);
			frm.toggle_display('column_break_p5_z2', true);
		}
	}
	
}

function update_main_section_visibility_simple(frm, type, prefix) {
	try {
		console.log(`🔧🔧🔧 update_main_section_visibility_simple aufgerufen: type=${type}, prefix=${prefix} ===`);
	
	const letter = type === 'standard' ? 's' : 'p';
	
		// Finde die letzte ausgefüllte Section (S1-S5 bzw P1-P5)
		let lastFilledIndex = -1;
	for (let num = 1; num <= 5; num++) {
			const mainNameField = `${prefix}${letter}${num}_1_name`;
			const mainCodeField = `${prefix}${letter}${num}_1_code`;
			const mainName = frm.doc[mainNameField];
			const mainCode = frm.doc[mainCodeField];
			
			console.log(`🔧 Prüfe ${letter.toUpperCase()}${num}: mainName='${mainName}', mainCode='${mainCode}'`);
		
		// Prüfe auch Varianten in dieser Section
		let hasVariants = false;
		for (let i = 2; i <= 6; i++) {
				const variantNameField = `${prefix}${letter}${num}_${i}_name`;
				const variantCodeField = `${prefix}${letter}${num}_${i}_code`;
			const variantName = frm.doc[variantNameField];
			const variantCode = frm.doc[variantCodeField];
			
			if ((variantName && variantName.trim()) || (variantCode && variantCode.trim())) {
				hasVariants = true;
					console.log(`🔧 ${letter.toUpperCase()}${num} hat Varianten: ${variantNameField}='${variantName}', ${variantCodeField}='${variantCode}'`);
				break;
			}
		}
		
		// Section ist ausgefüllt wenn Hauptfeld oder Varianten vorhanden sind
		if ((mainName && mainName.trim()) || (mainCode && mainCode.trim()) || hasVariants) {
				lastFilledIndex = num - 1; // S1=0, S2=1, etc.
				console.log(`🔧 ${letter.toUpperCase()}${num} ist ausgefüllt, lastFilledIndex = ${lastFilledIndex}`);
			}
		}
		
		console.log(`🔧 Letzte ausgefüllte Section: ${lastFilledIndex} (${letter.toUpperCase()}${lastFilledIndex + 1})`);
		
		// Steuere S2-S5 bzw P2-P5 Sections
		for (let num = 2; num <= 5; num++) {
			const sectionIndex = num - 1; // S2=1, S3=2, etc.
			const sectionField = `section_break_${letter}${num}${prefix ? '_z2' : ''}`;
			const nameField = `${prefix}${letter}${num}_1_name`;
			const codeField = `${prefix}${letter}${num}_1_code`;
			const columnBreakField = `column_break_${letter}${num}${prefix ? '_z2' : ''}`;
		
		// Zeige Section an wenn:
			// 1. Es ist eine ausgefüllte Section (sectionIndex <= lastFilledIndex)
			// 2. Es ist die nächste leere Section nach der letzten ausgefüllten (sectionIndex === lastFilledIndex + 1)
			let showSection = (sectionIndex <= lastFilledIndex + 1);
			
			console.log(`🔧 ${sectionField}: sectionIndex=${sectionIndex}, lastFilled=${lastFilledIndex}, zeigen=${showSection}`);
			console.log(`🔧 Felder: nameField='${nameField}', codeField='${codeField}', columnBreakField='${columnBreakField}'`);
			
			// ROBUSTE SICHTBARKEITS-ÄNDERUNG mit mehreren Methoden
			console.log(`🔧 ROBUSTE ÄNDERUNG für ${sectionField}: ${showSection ? 'sichtbar' : 'versteckt'}`);
			
			// Methode 1: frm.toggle_display
			frm.toggle_display(sectionField, showSection);
			frm.toggle_display(nameField, showSection);
			frm.toggle_display(codeField, showSection);
			frm.toggle_display(columnBreakField, showSection);
			
			// DEAKTIVIERT: Methode 2 kann Zuklappen verursachen
			// frm.set_df_property(sectionField, 'hidden', !showSection);
			// frm.set_df_property(nameField, 'hidden', !showSection);
			// frm.set_df_property(codeField, 'hidden', !showSection);
			// frm.set_df_property(columnBreakField, 'hidden', !showSection);
			
			// DEAKTIVIERT: DOM-Manipulation kann Zuklappen verursachen
			console.log(`ÜBERSPRUNGEN: DOM-Manipulation für ${sectionField} um Zuklappen zu vermeiden`);
		}
		
		// DEAKTIVIERT: refresh_fields kann Zuklappen verursachen
		// frm.refresh_fields();
		
		console.log(`🔧🔧🔧 update_main_section_visibility_simple ENDE: type=${type}, prefix=${prefix} ===`);
	} catch (error) {
		console.error(`❌❌❌ FEHLER in update_main_section_visibility_simple:`, error);
	}
}

function update_section_visibility_simple(frm, type, prefix) {
	console.log(`=== update_section_visibility_simple START: type=${type}, prefix='${prefix}' ===`);
	
	const letter = type === 'standard' ? 's' : 'p';
	
	// Finde die letzte ausgefüllte Section (S1-S5 bzw P1-P5)
	let lastFilledIndex = -1;
	for (let num = 1; num <= 5; num++) {
		const mainNameField = `${prefix}${letter}${num}_1_name`;
		const mainCodeField = `${prefix}${letter}${num}_1_code`;
		const mainName = frm.doc[mainNameField];
		const mainCode = frm.doc[mainCodeField];
		
		console.log(`Prüfe ${letter.toUpperCase()}${num}: mainName='${mainName}', mainCode='${mainCode}'`);
		
		// Prüfe auch Varianten in dieser Section
		let hasVariants = false;
		for (let i = 2; i <= 6; i++) {
			const variantNameField = `${prefix}${letter}${num}_${i}_name`;
			const variantCodeField = `${prefix}${letter}${num}_${i}_code`;
			const variantName = frm.doc[variantNameField];
			const variantCode = frm.doc[variantCodeField];
			
			if ((variantName && variantName.trim()) || (variantCode && variantCode.trim())) {
				hasVariants = true;
				console.log(`${letter.toUpperCase()}${num} hat Varianten: ${variantNameField}='${variantName}', ${variantCodeField}='${variantCode}'`);
				break;
			}
		}
		
		// Section ist ausgefüllt wenn Hauptfeld oder Varianten vorhanden sind
		if ((mainName && mainName.trim()) || (mainCode && mainCode.trim()) || hasVariants) {
			lastFilledIndex = num - 1; // S1=0, S2=1, etc.
			console.log(`${letter.toUpperCase()}${num} ist ausgefüllt, lastFilledIndex = ${lastFilledIndex}`);
		}
	}
	
	console.log(`Letzte ausgefüllte Section: ${lastFilledIndex} (${letter.toUpperCase()}${lastFilledIndex + 1})`);

	// Steuere Varianten-Sections (S1-S5 bzw P1-P5)
	for (let num = 1; num <= 5; num++) {
		const variantSectionField = `sb_${letter}${num}_variants${prefix ? '_z2' : ''}`;
		const sectionIndex = num - 1; // S1=0, S2=1, etc.
		
		// Prüfe ob diese spezifische Section ausgefüllt ist
		const mainNameField = `${prefix}${letter}${num}_1_name`;
		const mainCodeField = `${prefix}${letter}${num}_1_code`;
		const mainName = frm.doc[mainNameField];
		const mainCode = frm.doc[mainCodeField];
		const sectionFilled = (mainName && mainName.trim()) || (mainCode && mainCode.trim());
		
		// Varianten nur anzeigen wenn die entsprechende Hauptsection ausgefüllt ist
		let showSection = sectionFilled;
		
		console.log(`${variantSectionField}: sectionIndex=${sectionIndex}, ausgefüllt=${sectionFilled}, zeigen=${showSection}`);
		
		frm.toggle_display(variantSectionField, showSection);
		
		// IMMER progressive Varianten-Anzeige prüfen wenn Section sichtbar ist
		if (showSection) {
			handle_progressive_variants(frm, type, prefix, num);
		} else {
			// Section nicht sichtbar, alle Felder verstecken
			toggle_all_variant_fields(frm, type, prefix, num, false);
		}
		
		// ZUSÄTZLICHE SICHERHEIT: Auch wenn Section sichtbar ist, direkt progressive Logik anwenden
		if (showSection) {
			console.log(`🔧🔧 ZUSÄTZLICHE SICHERHEIT für ${variantSectionField}`);
			handle_progressive_variants_direct(frm, type, prefix, num);
		}
	}
	
	console.log(`=== update_section_visibility_simple ENDE: type=${type}, prefix='${prefix}' ===`);
}

function handle_progressive_variants_direct(frm, type, prefix, number) {
	const letter = type === 'standard' ? 's' : 'p';
	
	console.log(`🔧🔧 DIREKTE progressive Varianten für ${prefix}${letter}${number}`);
	
	// Prüfe ob das erste Feld (.1) ausgefüllt ist
	const firstNameField = `${prefix}${letter}${number}_1_name`;
	const firstCodeField = `${prefix}${letter}${number}_1_code`;
	const firstName = frm.doc[firstNameField];
	const firstCode = frm.doc[firstCodeField];
	
	const hasFirstField = !!(
		(firstName && firstName.trim()) || 
		(firstCode && firstCode.trim())
	);
	
	console.log(`🔧🔧 Erstes Feld (.1) ausgefüllt: ${hasFirstField}`);
	
	// Wenn erstes Feld leer ist, nur .1 und .2 anzeigen (immer eine leere Zeile)
	if (!hasFirstField) {
		console.log(`🔧🔧 Erstes Feld leer - zeige nur .1 und .2`);
		for (let i = 1; i <= 6; i++) {
			const nameField = `${prefix}${letter}${number}_${i}_name`;
			const codeField = `${prefix}${letter}${number}_${i}_code`;
			const shouldShow = i <= 2; // Immer .1 und .2 anzeigen
			frm.toggle_display(nameField, shouldShow);
			frm.toggle_display(codeField, shouldShow);
		}
		return;
	}
	
	// Erstes Feld (.1) immer anzeigen wenn Section sichtbar
	frm.toggle_display(firstNameField, true);
	frm.toggle_display(firstCodeField, true);
	
	// Finde den letzten ausgefüllten Index - prüfe von hinten nach vorne
	let lastFilledIndex = 1; // .1 ist immer sichtbar
	
	for (let i = 6; i >= 2; i--) {
		const nameField = `${prefix}${letter}${number}_${i}_name`;
		const codeField = `${prefix}${letter}${number}_${i}_code`;
		const name = frm.doc[nameField];
		const code = frm.doc[codeField];
		
		if ((name && name.trim()) || (code && code.trim())) {
			lastFilledIndex = i;
			console.log(`🔧🔧 Letztes ausgefülltes Feld gefunden: ${i}`);
			break; // Sofort stoppen wenn letztes ausgefülltes Feld gefunden
		}
	}
	
	// GARANTIERT mindestens eine leere Zeile nach der letzten ausgefüllten
	// Aber mindestens bis Feld .2 anzeigen (also immer mindestens .1 und .2)
	const minDisplayIndex = Math.max(lastFilledIndex + 1, 2);
	
	console.log(`🔧🔧 Progressive Anzeige: lastFilled=${lastFilledIndex}, minDisplay=${minDisplayIndex}`);
	
	for (let i = 2; i <= 6; i++) {
		const nameField = `${prefix}${letter}${number}_${i}_name`;
		const codeField = `${prefix}${letter}${number}_${i}_code`;
		
		// Zeige Feld wenn es ausgefüllt ist ODER wenn es mindestens bis minDisplayIndex gehen soll
		const showThisField = i <= minDisplayIndex;
		
		console.log(`🔧🔧 Feld ${i}: zeigen=${showThisField} (minDisplay=${minDisplayIndex})`);
		
		frm.toggle_display(nameField, showThisField);
		frm.toggle_display(codeField, showThisField);
	}
	
	// Column Break anzeigen wenn Section sichtbar
	const columnBreakField = `cb_${letter}${number}_variants${prefix ? '_z2' : ''}`;
	frm.toggle_display(columnBreakField, true);
}

function handle_progressive_variants(frm, type, prefix, number) {
	const letter = type === 'standard' ? 's' : 'p';
	
	// Prüfe ob das erste Feld (.1) ausgefüllt ist
	const firstNameField = `${prefix}${letter}${number}_1_name`;
	const firstCodeField = `${prefix}${letter}${number}_1_code`;
	const firstName = frm.doc[firstNameField];
	const firstCode = frm.doc[firstCodeField];
	
	const hasFirstField = !!(
		(firstName && firstName.trim()) || 
		(firstCode && firstCode.trim())
	);
	
	// Wenn erstes Feld leer ist, alle Varianten verstecken
	if (!hasFirstField) {
		toggle_all_variant_fields(frm, type, prefix, number, false);
		return;
	}
	
	// Erstes Feld (.1) immer anzeigen wenn Section sichtbar
	frm.toggle_display(firstNameField, true);
	frm.toggle_display(firstCodeField, true);
	
	// Progressive Anzeige für .2-.6 - zeige nur das nächste leere Feld
	let lastFilledIndex = 1; // .1 ist immer sichtbar
	
	// Finde den letzten ausgefüllten Index - prüfe von hinten nach vorne
	for (let i = 6; i >= 2; i--) {
		const nameField = `${prefix}${letter}${number}_${i}_name`;
		const codeField = `${prefix}${letter}${number}_${i}_code`;
		const name = frm.doc[nameField];
		const code = frm.doc[codeField];
		
		if ((name && name.trim()) || (code && code.trim())) {
			lastFilledIndex = i;
			break; // Sofort stoppen wenn letztes ausgefülltes Feld gefunden
		}
	}
	
	// GARANTIERT mindestens eine leere Zeile nach der letzten ausgefüllten
	// Aber mindestens bis Feld .2 anzeigen (also immer mindestens .1 und .2)
	const minDisplayIndex = Math.max(lastFilledIndex + 1, 2);
	
	console.log(`🔧 Progressive Anzeige für ${prefix}${letter}${number}: lastFilled=${lastFilledIndex}, minDisplay=${minDisplayIndex}`);
	
	for (let i = 2; i <= 6; i++) {
		const nameField = `${prefix}${letter}${number}_${i}_name`;
		const codeField = `${prefix}${letter}${number}_${i}_code`;
		
		// Zeige Feld wenn es ausgefüllt ist ODER wenn es mindestens bis minDisplayIndex gehen soll
		const showThisField = i <= minDisplayIndex;
		
		console.log(`🔧 Feld ${i}: zeigen=${showThisField} (minDisplay=${minDisplayIndex})`);
		
		frm.toggle_display(nameField, showThisField);
		frm.toggle_display(codeField, showThisField);
	}
	
	// Column Break anzeigen wenn Section sichtbar
	const columnBreakField = `cb_${letter}${number}_variants${prefix ? '_z2' : ''}`;
	frm.toggle_display(columnBreakField, true);
}

function toggle_all_variant_fields(frm, type, prefix, number, show) {
	const letter = type === 'standard' ? 's' : 'p';
	
	// Alle Subvarianten (1-6) für diese Kategorie
	for (let i = 1; i <= 6; i++) {
		const nameField = `${prefix}${letter}${number}_${i}_name`;
		const codeField = `${prefix}${letter}${number}_${i}_code`;
		
		frm.toggle_display(nameField, show);
		frm.toggle_display(codeField, show);
	}
	
	// Column Break auch steuern
	const columnBreakField = `cb_${letter}${number}_variants${prefix ? '_z2' : ''}`;
	frm.toggle_display(columnBreakField, show);
}

function update_variant_count_indicators(frm) {
	const current_period = frm.doc.period_editor;
	
	if (current_period === '1') {
		// Aktion 1: Standard S1-P5 und Premium P1-P5
		update_section_variant_count(frm, 'standard', '', 1, 5);
		update_section_variant_count(frm, 'premium', '', 1, 5);
	} else if (current_period === '2') {
		// Aktion 2: Standard S1-P5 und Premium P1-P5
		update_section_variant_count(frm, 'standard', 'z2_', 1, 5);
		update_section_variant_count(frm, 'premium', 'z2_', 1, 5);
	}
	
	// Sichtbarkeit wird jetzt korrekt durch update_section_visibility_simple gesteuert
}

function update_section_variant_count(frm, type, prefix, startNum, endNum) {
	const letter = type === 'standard' ? 's' : 'p';
	
	// Hilfsfunktion um Zahlen in Wörter umzuwandeln
	function numberToWords(num) {
		const words = {
			1: 'eine',
			2: 'zwei', 
			3: 'drei',
			4: 'vier',
			5: 'fünf',
			6: 'sechs'
		};
		return words[num] || num.toString();
	}
	
	for (let number = startNum; number <= endNum; number++) {
		const sectionField = `sb_${letter}${number}_variants${prefix ? '_z2' : ''}`;
		
		// Zähle befüllte Varianten (2-6, da 1 das Hauptfeld ist)
		let filledCount = 0;
		for (let i = 2; i <= 6; i++) {
			const nameField = `${prefix}${letter}${number}_${i}_name`;
			const codeField = `${prefix}${letter}${number}_${i}_code`;
			const name = frm.doc[nameField];
			const code = frm.doc[codeField];
			
			if ((name && name.trim()) || (code && code.trim())) {
				filledCount++;
			}
		}
		
		// Update Section Break Label
		if (frm.fields_dict[sectionField]) {
			const typeLabel = type === 'standard' ? 'Standard' : 'Premium';
			const baseLabel = `Varianten ${typeLabel} ${number}`;
			const countIndicator = filledCount > 0 ? ` <span style="color:rgb(69, 92, 142); font-weight: bold;">${numberToWords(filledCount)} befüllt</span>` : '';
			const newLabel = baseLabel + countIndicator;
			
			console.log(`Updating ${sectionField}: ${newLabel}`);
			
			// VORSICHTIGER DOM Update ohne Section-Manipulation
			console.log(`Versuche vorsichtiges Label-Update für ${sectionField}: ${newLabel}`);
			
			// Nur Text-Update ohne strukturelle Änderungen
			setTimeout(() => {
				try {
					// Sehr spezifischer Selector nur für den Text-Inhalt
					const textSelector = `[data-fieldname="${sectionField}"] .section-head`;
					const elements = $(textSelector);
					
					if (elements.length === 1) {
						// HTML-Update mit Farbe, aber vorsichtig
						const currentText = elements.text().trim();
						if (currentText && !currentText.includes(numberToWords(filledCount))) {
							elements.html(newLabel); // HTML mit Farbe beibehalten
							console.log(`✅ SICHERER HTML-Update für ${sectionField}: ${newLabel}`);
						}
					}
				} catch (error) {
					console.log(`⚠️ Sicherer Update fehlgeschlagen für ${sectionField}:`, error);
				}
			}, 300); // Längere Verzögerung für Stabilität
		} else {
			console.log(`Field ${sectionField} not found!`);
		}
	}
}

function update_schwellwerte_labels(frm) {
	const label1 = frm.doc.period_1_label || 'Aktion 1';
	const label2 = frm.doc.period_2_label || 'Aktion 2';
	
	// Sichere Label-Updates mit verbesserter Stabilität
	console.log(`Updating Schwellwerte Labels: ${label1}, ${label2}`);
	
	// Verwende einen sichereren Ansatz mit längerer Verzögerung
	setTimeout(() => {
		try {
			// Sicherer DOM-Update mit stabileren Selektoren
			update_schwellwerte_section_labels(frm, 'section_break_schwellwerte', `Aktions-Schwellwerte ${label1}`);
			update_schwellwerte_section_labels(frm, 'section_break_schwellwerte_z2', `Aktions-Schwellwerte ${label2}`);
		} catch (error) {
			console.log(`⚠️ Fehler beim Label-Update:`, error);
		}
	}, 500); // Längere Verzögerung für bessere Stabilität
}

function update_schwellwerte_section_labels(frm, fieldname, newLabel) {
	console.log(`=== SICHERER UPDATE für Section Break ${fieldname} ===`);
	console.log(`Neues Label: ${newLabel}`);
	
	// Sicherere Selektor-Strategie mit spezifischeren Zielen
	const targetSelector = `[data-fieldname="${fieldname}"]`;
	const sectionElement = $(targetSelector);
	
	if (sectionElement.length) {
		// Versuche verschiedene Label-Selektoren in Reihenfolge der Präferenz
		const labelSelectors = [
			'.section-head h6',
			'.section-head .section-title', 
			'.section-head',
			'h6',
			'.form-section-head'
		];
		
		let updated = false;
		for (const selector of labelSelectors) {
			const labelElement = sectionElement.find(selector).first();
			if (labelElement.length && labelElement.text().includes('Aktions-Schwellwerte')) {
				console.log(`Label gefunden mit Selektor: ${selector}`);
				labelElement.text(newLabel);
				console.log(`✅ Label erfolgreich aktualisiert: ${newLabel}`);
				updated = true;
				break;
			}
		}
		
		if (!updated) {
			console.log(`⚠️ Kein passender Label-Selektor für ${fieldname} gefunden`);
		}
	} else {
		console.log(`⚠️ Section Element ${fieldname} nicht gefunden`);
	}
	
	console.log(`=== ENDE SICHERER UPDATE für ${fieldname} ===`);
}

function update_section_break_dom_label(frm, fieldname, newLabel) {
	console.log(`=== DOM UPDATE für Section Break ${fieldname} ===`);
	console.log(`Neues Label: ${newLabel}`);
	
	// Verschiedene Selektoren für Section Break Labels
	const selectors = [
		`[data-fieldname="${fieldname}"] .section-head`,
		`[data-fieldname="${fieldname}"] h6`,
		`[data-fieldname="${fieldname}"] .section-title`,
		`[data-fieldname="${fieldname}"] .label`,
		`[data-fieldname="${fieldname}"] .form-label`,
		`[data-fieldname="${fieldname}"] .field-label`,
		`[data-fieldname="${fieldname}"] .section-head h6`,
		`[data-fieldname="${fieldname}"] .section-head .section-title`
	];
	
	let updated = false;
	for (const selector of selectors) {
		const elements = $(selector);
		console.log(`Selektor ${selector}: ${elements.length} Elemente gefunden`);
		if (elements.length && !updated) {
			elements.html(newLabel);
			console.log(`✅ DOM Update für ${fieldname} mit Selektor ${selector}: ${newLabel}`);
			updated = true;
		}
	}
	
	// Fallback: Suche nach Text-Inhalt
	if (!updated) {
		console.log(`Fallback: Suche nach "Aktions-Schwellwerte"`);
		const textElements = $('*').filter(function() {
			const text = $(this).text().trim();
			return text.startsWith('Aktions-Schwellwerte') && text.length < 50; // Nicht zu lang
		});
		console.log(`Text-Elemente gefunden: ${textElements.length}`);
		if (textElements.length) {
			textElements.first().html(newLabel);
			console.log(`✅ Fallback DOM Update für ${fieldname}: ${newLabel}`);
			updated = true;
		}
	}
	
	console.log(`=== ENDE DOM UPDATE für ${fieldname} ===`);
}


