    async def _process_with_mistral(self, text: str) -> Dict[str, Any]:
        """Process CV text with Mistral 7B for structured extraction"""
        try:
            # Prepare the prompt for Mistral
            prompt = f"""Extract the following information from this CV in JSON format:
            - name
            - email
            - phone
            - title/position
            - skills (list)
            - experience (list of objects with position, company, start_date, end_date, description)
            - education (list of objects with degree, institution, year)
            - certifications (list)
            - languages (list)
            - linkedin (url)
            - github (url)
            - website (url)
            
            CV Content:
            {text}
            
            Return ONLY the JSON object, no other text."""
            
            # Call Ollama API
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.ollama_client.chat(
                    model='mistral',
                    messages=[{'role': 'user', 'content': prompt}]
                )
            )
            
            # Extract and parse the response
            if response and 'message' in response and 'content' in response['message']:
                content = response['message']['content']
                # Clean up the response to ensure it's valid JSON
                json_str = self._clean_json_response(content)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON response: {json_str}")
                    return {}
            return {}
            
        except Exception as e:
            print(f"Mistral processing error: {e}")
            return {}
