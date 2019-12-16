.PHONY: zip
zip:
	@rm -rf function.zip
	@zip -r function lambda_function.py > /dev/null
